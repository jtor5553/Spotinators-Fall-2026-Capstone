(function () {
  var statusUrl = "/api/status";
  var latest = null;
  var cameraTimer = null;
  var cameraInFlight = false;
  var cameraScheduleKey = "";
  var holdTimer = null;
  var sourceKey = "";
  var credentialsApplied = false;
  var statusInFlight = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json();
    }).then(function (payload) {
      if (payload && payload.message) {
        byId("message-line").textContent = payload.message;
      }
      refresh();
    }).catch(function () {
      byId("message-line").textContent = "The Jetson did not answer. The robot program is still the controller.";
    });
  }

  function refresh() {
    if (statusInFlight) {
      return;
    }
    statusInFlight = true;
    fetch(statusUrl, { cache: "no-store" })
      .then(function (response) { return response.json(); })
      .then(render)
      .catch(function () {
        byId("message-line").textContent = "Waiting for the Jetson controller.";
      })
      .then(function () {
        statusInFlight = false;
      });
  }

  function render(status) {
    latest = status;
    var connected = status.spot.connection === "CONNECTED";
    byId("connect-screen").classList.toggle("hidden", connected);
    byId("main-screen").classList.toggle("hidden", !connected);
    fillSaved(status);
    byId("state-pill").textContent = status.state;
    byId("connect-status").textContent = status.spot.connection;
    byId("estop-banner").classList.toggle("hidden", !status.estop_active);
    byId("warning-banner").classList.toggle("hidden", !status.warning);
    byId("warning-banner").textContent = status.warning || "";
    renderSpot(status);
    renderPad(status);
    renderDispenser(status);
    renderCommands(status);
    renderCameras(status);
    renderLog(status);
  }

  function fillSaved(status) {
    if (status.spot.connection === "CONNECTED" || credentialsApplied) {
      return;
    }
    credentialsApplied = true;
    byId("robot-ip").value = status.saved_hostname || "";
    byId("username").value = status.saved_username || "user2";
    byId("password").value = status.saved_password || "";
    byId("remember").checked = Boolean(
      status.saved_hostname || status.saved_username || status.saved_password
    );
  }

  function renderSpot(status) {
    var spot = status.spot;
    byId("spot-connection").textContent = spot.connection === "CONNECTED" ? "Connected" : "Not connected";
    setDot("spot-dot", spot.connection === "CONNECTED");
    byId("spot-battery").textContent = spot.battery === null || spot.battery === undefined ? "--" : spot.battery + "%";
    byId("spot-posture").textContent = spot.robot_state || "Unknown";
    byId("spot-motors").textContent = motorLine(spot);
    var velocity = spot.velocity || [0, 0, 0];
    byId("spot-speed").textContent = "Velocity " + velocity.map(formatNum).join(", ");
  }

  function motorLine(spot) {
    var text = spot.motors || "--";
    if (spot.motor_error) {
      text += " — " + spot.motor_error;
    }
    var faults = spot.behavior_faults || [];
    if (faults.length) {
      text += " — " + faults.map(function (fault) { return fault.cause; }).join(", ");
    }
    return text;
  }

  function renderPad(status) {
    var pad = status.controller;
    var label = pad.message || (pad.connected ? "Connected" : "Not connected");
    byId("pad-connection").textContent = label;
    setDot("pad-dot", pad.connected);
    byId("pad-r2").textContent = pad.r2_held ? "Held " + Math.round(pad.r2 * 100) + "%" : "Released";
    byId("left-x").textContent = formatNum(pad.left.x);
    byId("left-y").textContent = formatNum(pad.left.y);
    byId("right-x").textContent = formatNum(pad.right.x);
    byId("right-y").textContent = formatNum(pad.right.y);
    byId("button-x").textContent = pad.buttons.x ? "Held" : "Released";
    byId("button-lb").textContent = pad.buttons.lb ? "Held" : "Released";
    byId("button-rb").textContent = pad.buttons.rb ? "Held" : "Released";
    byId("button-options").textContent = pad.buttons.options ? "Held" : "Released";
  }

  function renderDispenser(status) {
    var dispenser = status.dispenser;
    byId("dispenser-state").textContent = dispenser.state;
    byId("cone-count").textContent = dispenser.cones_remaining;
    byId("cone-reset").textContent = "Reset to " + dispenser.capacity;
    var progress = Math.round((status.drop_hold_progress || 0) * 100);
    byId("drop-progress").textContent = progress ? "Hold progress " + progress + "%" : "";
    setDot("cone-dot", dispenser.state === "READY", dispenser.state === "FAULT" || dispenser.state === "DISABLED");
  }

  function renderCommands(status) {
    var commands = status.commands;
    byId("stand-button").disabled = !commands.stand;
    byId("sit-button").disabled = !commands.sit;
    byId("arm-button").disabled = !commands.arm;
    byId("resume-button").disabled = !commands.resume;
    byId("drop-cone").disabled = !commands.drop;
    byId("cone-minus").disabled = !commands.adjust_cones;
    byId("cone-plus").disabled = !commands.adjust_cones;
    byId("cone-reset").disabled = !commands.adjust_cones;
    byId("reset-estop").classList.toggle("hidden", !commands.reset_estop);
    byId("arm-button").classList.toggle("hidden", !commands.arm);
    byId("resume-button").classList.toggle("hidden", !commands.resume);
  }

  function renderCameras(status) {
    var sources = status.camera.sources || [];
    var key = sources.join("|") + ":" + status.camera.selected;
    if (key !== sourceKey) {
      sourceKey = key;
      var box = byId("camera-buttons");
      box.innerHTML = "";
      sources.forEach(function (name) {
        var button = document.createElement("button");
        button.type = "button";
        button.textContent = name;
        button.className = name === status.camera.selected ? "action" : "secondary";
        button.addEventListener("click", function () {
          post("/api/cameras/select", { name: name });
        });
        box.appendChild(button);
      });
    }
    scheduleCamera(status);
  }

  function scheduleCamera(status) {
    var selected = status.camera.selected || "";
    var fps = status.camera.fps || 10;
    var key = selected + ":" + fps;
    if (!selected) {
      if (cameraTimer) {
        clearTimeout(cameraTimer);
        cameraTimer = null;
      }
      cameraScheduleKey = "";
      cameraInFlight = false;
      return;
    }
    if (key === cameraScheduleKey) {
      return;
    }
    cameraScheduleKey = key;
    if (cameraTimer) {
      clearTimeout(cameraTimer);
      cameraTimer = null;
    }
    cameraInFlight = false;
    var image = byId("camera-image");
    var delay = Math.max(100, Math.round(1000 / fps));

    function armNext() {
      if (cameraScheduleKey !== key) {
        return;
      }
      cameraTimer = setTimeout(load, delay);
    }

    function load() {
      if (cameraScheduleKey !== key) {
        return;
      }
      if (cameraInFlight) {
        armNext();
        return;
      }
      cameraInFlight = true;
      image.onload = function () {
        cameraInFlight = false;
        armNext();
      };
      image.onerror = function () {
        cameraInFlight = false;
        armNext();
      };
      image.src = "/api/camera/frame?t=" + Date.now();
    }

    load();
  }

  function renderLog(status) {
    var list = byId("log-list");
    list.innerHTML = "";
    (status.log || []).forEach(function (entry) {
      var item = document.createElement("li");
      item.textContent = entry.time + " " + entry.message;
      list.appendChild(item);
    });
  }

  function setDot(id, good, bad) {
    var dot = byId(id);
    dot.className = "dot " + (bad ? "off" : good ? "on" : "warn");
  }

  function formatNum(value) {
    var number = Number(value || 0);
    return number.toFixed(2);
  }

  function bindHold(id) {
    var button = byId(id);
    function send(pressed) {
      fetch("/api/cone/hold", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pressed: pressed })
      }).catch(function () { });
    }
    function start(event) {
      event.preventDefault();
      send(true);
      holdTimer = setInterval(function () { send(true); }, 100);
    }
    function end() {
      clearInterval(holdTimer);
      send(false);
    }
    button.addEventListener("pointerdown", start);
    button.addEventListener("pointerup", end);
    button.addEventListener("pointerleave", end);
    button.addEventListener("pointercancel", end);
    button.addEventListener("contextmenu", function (event) { event.preventDefault(); });
  }

  byId("connect-button").addEventListener("click", function () {
    post("/api/connect", {
      hostname: byId("robot-ip").value,
      username: byId("username").value,
      password: byId("password").value,
      remember: byId("remember").checked,
      mock: byId("mock-mode").checked
    });
  });
  byId("stand-button").addEventListener("click", function () { post("/api/stand"); });
  byId("sit-button").addEventListener("click", function () { post("/api/sit"); });
  byId("stop-button").addEventListener("click", function () { post("/api/stop"); });
  byId("estop-button").addEventListener("click", function () { post("/api/estop"); });
  byId("reset-estop").addEventListener("click", function () { post("/api/estop/reset"); });
  byId("arm-button").addEventListener("click", function () { post("/api/arm"); });
  byId("resume-button").addEventListener("click", function () { post("/api/resume"); });
  byId("sign-out-button").addEventListener("click", function () {
    credentialsApplied = false;
    post("/api/signout");
  });
  byId("cone-minus").addEventListener("click", function () { post("/api/cone/adjust", { delta: -1 }); });
  byId("cone-plus").addEventListener("click", function () { post("/api/cone/adjust", { delta: 1 }); });
  byId("cone-reset").addEventListener("click", function () { post("/api/cone/reset"); });
  byId("cone-reverse").addEventListener("click", function () { post("/api/cone/reverse"); });
  byId("cone-home").addEventListener("click", function () { post("/api/cone/home"); });
  byId("bluetooth-button").addEventListener("click", function () {
    fetch("/api/bluetooth").then(function (response) { return response.json(); }).then(function (payload) {
      var lines = [payload.message || ""];
      (payload.devices || []).forEach(function (device) {
        lines.push(device.name + " " + device.address);
      });
      byId("bluetooth-list").textContent = lines.join("\n");
    });
  });
  function initTheme() {
    var storedTheme = localStorage.getItem("spot_theme");
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var currentTheme = storedTheme || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", currentTheme);

    var toggleBtn = byId("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        var active = document.documentElement.getAttribute("data-theme") || "dark";
        var next = active === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("spot_theme", next);
      });
    }
  }

  initTheme();
  bindHold("drop-cone");
  refresh();
  setInterval(refresh, 100);
})();

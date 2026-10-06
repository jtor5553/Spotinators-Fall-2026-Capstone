"""Software E-stop endpoint. This does not replace Spot's physical E-stop."""


class SpotEStop:
    def __init__(self, timeout_sec=9.0):
        self.timeout_sec = timeout_sec
        self.endpoint = None
        self.keepalive = None

    def setup(self, robot):
        if self.endpoint is not None and self.keepalive is not None:
            return
        from bosdyn.client.estop import EstopClient, EstopEndpoint, EstopKeepAlive

        client = robot.ensure_client(EstopClient.default_service_name)
        endpoint = EstopEndpoint(client, name="spot-cone-controller", estop_timeout=self.timeout_sec)
        endpoint.force_simple_setup()
        self.endpoint = endpoint
        self.keepalive = EstopKeepAlive(endpoint)

    def stop(self):
        if self.keepalive is not None:
            self.keepalive.stop()
        elif self.endpoint is not None:
            self.endpoint.stop()

    def allow(self):
        if self.keepalive is not None:
            self.keepalive.allow()
        elif self.endpoint is not None:
            self.endpoint.allow()

    def shutdown(self):
        if self.keepalive is not None:
            try:
                self.keepalive.shutdown()
            except Exception:
                pass
            self.keepalive = None
        if self.endpoint is not None:
            try:
                self.endpoint.deregister()
            except Exception:
                pass
            self.endpoint = None

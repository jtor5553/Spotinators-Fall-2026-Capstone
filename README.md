# Spotinators Fall 2026 Capstone

A Boston Dynamics Spot robot tows a small trailer that drops traffic cones. The program on the trailer is the controller. The Spot tablet only opens that program in a browser. It does not drive the robot.

The page title is **Spot Cone Placement System**. Practice it on a Windows PC first. Connect Spot and the cone motor later, on the Jetson.

## Start here

Pick the computer you are sitting at.

- **[Windows setup](WINDOWS_SETUP.md).** Practice the page, and drive with a PG-9083S gamepad. Spot and the motor stay mocked.
- **[Jetson setup](JETSON_SETUP.md).** Set up the Orin Nano on the trailer: the PS5 controller, Spot, the cone motor, the Spot tablet over Spot's Wi-Fi, and starting at boot.

Read the safety rules below before either computer is connected to the real robot.

## Safety

- Driving starts disabled. The motor starts off.
- If a saved IP, username, and password are present, starting the program connects to the real robot, takes the lease, and stands. It does not continue an old move or an old motor command.
- Sticks do nothing until Spot is standing and driving is enabled.
- If the gamepad disconnects, Spot stops and cone drops are disabled.
- Stop and Emergency stop are different controls. Emergency stop has no confirmation question.
- The software E-stop does not replace Spot's physical E-stop, or the mushroom E-stop on the trailer.
- Do the first real tests in a closed lot, not in traffic.
- The Spot password can be remembered in `config/operator.yaml`. Do not put it in `config.yaml`.

Speed limits, the button list, and what to do when a screen looks wrong are in the setup guide for the computer you are using.

## What is in this repository

```text
WINDOWS_SETUP.md          practice on a Windows PC
JETSON_SETUP.md           Orin Nano setup, from install through boot
spot_cone_controller/     the program
  main.py                 starts the controller and the web page
  gui/                    the touchscreen page
  controller/             stick mapping, DualSense reader, Windows gamepad reader
  spot/                   real Spot connection
  dispenser/              cone motor
  config/                 settings. Do not store the Spot password in config.yaml.
```

The page and the gamepad both send requests to one controller. That controller decides what is allowed. Autonomy, GPS routes, and automatic cone spacing are not in this version.

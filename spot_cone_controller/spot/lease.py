"""Lease used only after the operator asks the robot to stand or drive."""


class LeaseManager:
    def __init__(self):
        self.keepalive = None

    def acquire(self, robot):
        from bosdyn.client.lease import LeaseClient, LeaseKeepAlive

        if self.keepalive is not None:
            return
        client = robot.ensure_client(LeaseClient.default_service_name)
        self.keepalive = LeaseKeepAlive(client, must_acquire=True, return_at_exit=True)

    def release(self):
        if self.keepalive is None:
            return
        try:
            self.keepalive.shutdown()
        finally:
            self.keepalive = None

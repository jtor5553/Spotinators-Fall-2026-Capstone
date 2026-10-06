"""Lease used only after the operator asks the robot to stand or drive."""


class LeaseManager:
    def __init__(self):
        self.keepalive = None
        self.lost = False
        self.failure = ""

    def acquire(self, robot):
        from bosdyn.client.lease import LeaseClient, LeaseKeepAlive

        if self.keepalive is not None and not self.lost:
            return
        if self.keepalive is not None:
            self.release()
        client = robot.ensure_client(LeaseClient.default_service_name)
        self.keepalive = LeaseKeepAlive(
            client,
            must_acquire=True,
            return_at_exit=True,
            on_failure_callback=self._on_failure,
        )
        self.lost = False
        self.failure = ""

    def needs_reacquire(self):
        return self.keepalive is None or self.lost

    def _on_failure(self, exc):
        # The keepalive thread calls this. Reacquire happens later on the control thread.
        self.lost = True
        self.failure = str(exc)

    def release(self):
        if self.keepalive is None:
            return
        try:
            self.keepalive.shutdown()
        finally:
            self.keepalive = None

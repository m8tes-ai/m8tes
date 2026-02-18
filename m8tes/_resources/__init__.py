"""Resource namespaces for the v2 developer SDK."""

from .apps import Apps
from .memories import Memories
from .permissions import Permissions
from .runs import Runs
from .settings import Settings
from .tasks import Tasks
from .teammates import Teammates
from .users import Users
from .webhooks import Webhooks

__all__ = [
    "Apps",
    "Memories",
    "Permissions",
    "Runs",
    "Settings",
    "Tasks",
    "Teammates",
    "Users",
    "Webhooks",
]


from plugin_sqlite_backup import copy_to_backup

def backup_db():
    """
    A controller function to execute the copy_to_backup() module function.

    Returns a dictionary with a single key, 'success'. On success of the
    backup this value will be True, and on failure it will be False.

    """
    success = copy_to_backup()
    return {'success': success}

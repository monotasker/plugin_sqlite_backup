"""
Plugin_backup

This web2py plugin provides functions to safely backup the sqlite database
for a web2py application.

This version Ian W. Scott (monotasker)

This is just a light revision of the code posted by @peter on the
web2py-users discussion group here:
https://groups.google.com/forum/?nomobile=true#!searchin/web2py/backup$20sqlite/web2py/p1QeoKltkL8/iFrm6AHGahoJ

"""


from gluon import current
import sqlite3
import shutil
import time
import os
import traceback
import zipfile
from dropbox import client, session  # rest


def copy_db(mydir=None):
    """
    Make a backup copy of sqlite database file.

    By default the backup is saved to myapp/backup/. If successful, the
    function returns the full path of the backup file. If unsuccessful, it
    returns False.

    """
    try:
        request = current.request
        print('request.folder is', request.folder)
        sourcefile = os.path.join(request.folder, 'databases/storage.sqlite')
        print('sourcefile is', sourcefile)
        target_dir = os.path.join(request.folder, 'backup')
        print('target_dir is', target_dir)
        mytime = time.strftime(".%Y-%m-%d-%H%M")
        backfilename = os.path.basename(sourcefile) + mytime
        backupfile = os.path.join(target_dir, backfilename)
        print('backupfile is', backupfile)

        db = sqlite3.connect(sourcefile)
        cur = db.cursor()
        cur.execute('begin immediate')

        shutil.copyfile(sourcefile, backupfile)
        db.rollback()
        return backupfile
    except Exception:
        print(traceback.format_exc(5))
        return False


def do_zip_except_sqlite(target_dir, file_name):
    """
    Compress all db files not ending in .sqlite and copy to the target_dir.

    By default the backup is saved to myapp/backup/. If successful, the
    function returns the full path of the backup file. If unsuccessful, it
    returns False.

    """
    try:
        zip = zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED)
        rootlen = len(target_dir) + 1
        #print rootlen
        for base, dirs, files in os.walk(target_dir):
            #print dir
            filelist = []
            for file in files:
                if file.find('.sqlite', len(file) - 7) == -1:
                    fn = os.path.join(base, file)
                    zip.write(fn, fn[rootlen:])
                    filelist.append(fn)
        zip.close()
        return filelist
    except Exception:
        print(traceback.format_exc(5))
        return False


def copy_to_backup():
    """
    This uses both routines to copy the database files to the backup directory.
    It time stamps their names.

    By default the backup is saved to myapp/backup/. If successful, the
    function returns a two-member list of the two backup files created. If
    unsuccessful, it returns False.
    """
    try:
        request = current.request
        backupfile = os.path.join(request.folder, 'backup/databases.zip' + time.strftime(".%Y%m%d-%H%M"))
        myfile1 = do_zip_except_sqlite(os.path.join(request.folder, 'databases'), backupfile)
        myfile2 = copy_db()
        return [myfile2, myfile1]
    except Exception:
        print(traceback.format_exc(5))
        return False


def filelocs(tokenfile=None, keyfile=None, targetdir=None):
    """
    Provide file and directory locations for the other functions.
    """
    request = current.request
    app = request.application
    t_default = 'applications/{}/dropbox_token.txt'.format(app)
    k_default = 'applications/{}/private/dropbox.keys'.format(app)
    dir_default = 'applications/{}/backup'.format(app)
    keyfile = k_default if not keyfile else keyfile
    tokenfile = t_default if not tokenfile else tokenfile
    targetdir = dir_default if not targetdir else targetdir

    return tokenfile, keyfile, targetdir


def dropbox_connect(tokenfile, keyfile):
    """
    Initialize an open connection with the configured dropbox account.
    """
    # Get your app key and secret from the Dropbox developer website
    with open(keyfile, 'r') as mykeys:
        keydata = {k: v for line in mykeys for k, v in line.split()}
        APP_KEY = keydata['app_key']
        APP_SECRET = keydata['app_secret']

    ACCESS_TYPE = 'app_folder'
    with open(tokenfile, 'r') as mytoken:
        TOKEN_KEY, TOKEN_SECRET = mytoken.split('|')

    sess = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)
    sess.set_token(TOKEN_KEY, TOKEN_SECRET)

    return sess


def backup_to_dropbox(tokenfile=None, keyfile=None, targetdir=None):
    """
        Copy backup files from myapp/backup folder to dropbox.

        By default this function looks for the dropbox access token in
        applications/my_app/private/dropbox_token.txt. It looks for the dropbox
        key and secret in applications/my_app/private/dropbox.keys. Either (or both)
        of these locations can be overridden with the 'tokenfile' and 'keyfile'
        keyword arguments.

        Writing it to this file means that permission only has to be given once
        per application.

        TODO: encrypt the dropbox token, possibly hashed in the db?

    """
    #token = current.session.token  # ????
    tokenfile, keyfile, targetdir = filelocs(tokenfile, keyfile, targetdir)
    dropbox_session = dropbox_connect(tokenfile, keyfile)
    client = client.DropboxClient(dropbox_session)

    rootlen = len(targetdir) + 1
    for base, dirs, files in os.walk(targetdir):
        for file in files:
            f = open(targetdir + '/' + file)
            client.put_file('f1/' + file, f)
            f.close()
    written = os.walk(targetdir)

    return {'base': written[0], 'dirs': written[1], 'files': written[2]}


def setup_dropbox(tokenfile=None, keyfile=None, targetdir=None):
    """
    Set up a connection with a Dropbox account for later access.

    To set up dropbox you need two routines: one to do the initial setting up,
    and one to 'redirect' to after the permission has been granted.

    """
    # Get your app key and secret from the Dropbox developer website
    tokenfile, keyfile, targetdir = filelocs(tokenfile, keyfile, targetdir)
    dropbox_session = dropbox_connect(tokenfile, keyfile)

    request_token = sess.obtain_request_token()

    urlbase = URL('finish_setup_dropbox', scheme=True, host=True)
    url = sess.build_authorize_url(request_token, urlbase)
    current.session.token = (request_token.key, request_token.secret)

    TOKENS = tokenfile
    token_file = open(TOKENS, 'w')
    token_file.write("{}|{}".format(request_token.key, request_token.secret))
    token_file.close()
    redirect(url)
    return True


def finish_setup_dropbox(tokenfile=None, keyfile=None, targetdir=None):
    """
    Catch the redirection after the permission has been given by dropbox server.
    """
    tokenfile, keyfile, targetdir = filelocs(tokenfile, keyfile, targetdir)
    dropbox_session = dropbox_connect(tokenfile, keyfile)

    request_token = dropbox_session.obtain_request_token()
    with open(tokenfile_r, 'r') as mytoken_r:  # needs to be tokenr.txt  -- also in dropbox_connect
        request_token.key, request_token.secret = mytoken_r.split('|')

    access_token = sess.obtain_access_token(request_token)
    with open(tokenfile, 'w') as mytoken:
        mytoken.write("{}|{}".format(access_token.key, access_token.secret))

    client = client.DropboxClient(sess)
    # print "linked account:", client.account_info()

    return True

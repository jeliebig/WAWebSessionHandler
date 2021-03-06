import json
import logging
import os
import platform
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

CHROME = 1
FIREFOX = 2


class SessionHandler:
    __URL = 'https://web.whatsapp.com/'

    def __init_browser(self):
        self.log.debug("Setting browser user dirs...")
        if self.__browser_choice == CHROME:
            self.__browser_options = webdriver.ChromeOptions()

            if self.__platform == 'windows':
                self.__browser_user_dir = os.path.join(os.environ['USERPROFILE'],
                                                       'Appdata', 'Local', 'Google', 'Chrome', 'User Data')
            elif self.__platform == 'linux':
                self.__browser_user_dir = os.path.join(os.environ['HOME'], '.config', 'google-chrome')

        elif self.__browser_choice == FIREFOX:
            self.__browser_options = webdriver.FirefoxOptions()

            if self.__platform == 'windows':
                self.__browser_user_dir = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles')
                self.__browser_profile_list = os.listdir(self.__browser_user_dir)
            elif self.__platform == 'linux':
                self.__browser_user_dir = os.path.join(os.environ['HOME'], '.mozilla', 'firefox')

        self.log.debug('Browser user dirs set.')

        self.__browser_options.headless = True
        self.__refresh_profile_list()

    def __refresh_profile_list(self):
        self.log.debug('Getting browser profiles...')
        if self.__browser_choice == CHROME:
            self.__browser_profile_list = ['']
            for profile_dir in os.listdir(self.__browser_user_dir):
                if 'profile' in profile_dir.lower():
                    if profile_dir != 'System Profile':
                        self.__browser_profile_list.append(profile_dir)
        elif self.__browser_choice == FIREFOX:
            # TODO: consider reading out the profiles.ini
            self.__browser_profile_list = []
            for profile_dir in os.listdir(self.__browser_user_dir):
                if not profile_dir.endswith('.default'):
                    if os.path.isdir(os.path.join(self.__browser_user_dir, profile_dir)):
                        self.__browser_profile_list.append(profile_dir)

        self.log.debug('Browser profiles registered.')

    def __get_indexed_db(self):
        self.log.debug('Executing getIDBObjects function...')
        self.__driver.execute_script('window.waScript = {};'
                                     'window.waScript.waSession = undefined;'
                                     'function getAllObjects() {'
                                     'window.waScript.dbName = "wawc";'
                                     'window.waScript.osName = "user";'
                                     'window.waScript.db = undefined;'
                                     'window.waScript.transaction = undefined;'
                                     'window.waScript.objectStore = undefined;'
                                     'window.waScript.getAllRequest = undefined;'
                                     'window.waScript.request = indexedDB.open(window.waScript.dbName);'
                                     'window.waScript.request.onsuccess = function(event) {'
                                     'window.waScript.db = event.target.result;'
                                     'window.waScript.transaction = window.waScript.db.transaction('
                                     'window.waScript.osName);'
                                     'window.waScript.objectStore = window.waScript.transaction.objectStore('
                                     'window.waScript.osName);'
                                     'window.waScript.getAllRequest = window.waScript.objectStore.getAll();'
                                     'window.waScript.getAllRequest.onsuccess = function(getAllEvent) {'
                                     'window.waScript.waSession = getAllEvent.target.result;'
                                     '};'
                                     '};'
                                     '}'
                                     'getAllObjects();')
        self.log.debug('Waiting until IDB operation finished...')
        while not self.__driver.execute_script('return window.waScript.waSession != undefined;'):
            time.sleep(1)
        self.log.debug('Getting IDB results...')
        wa_session_list = self.__driver.execute_script('return window.waScript.waSession;')
        self.log.debug('Got IDB data: %s', wa_session_list)
        return wa_session_list

    def __get_profile_storage(self, profile_name=None):
        self.__refresh_profile_list()

        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError('The specified profile_name was not found. Make sure the name is correct.')

        if profile_name is None:
            self.__start_visible_session()
        else:
            self.__start_invisible_session(profile_name)

        indexed_db = self.__get_indexed_db()

        self.log.debug("Closing browser...")
        self.__driver.quit()

        return indexed_db

    def __start_session(self, options, profile_name=None, wait_for_login=True):
        self.log.debug('Starting browser... [HEADLESS: %s]', str(options.headless))
        if profile_name is None:
            if self.__browser_choice == CHROME:
                self.__driver = webdriver.Chrome(options=options)
            elif self.__browser_choice == FIREFOX:
                self.__driver = webdriver.Firefox(options=options)

            self.log.debug('Loading WhatsApp Web...')
            self.__driver.get(self.__URL)

            if wait_for_login:
                self.log.debug('Waiting for login...')
                verified_wa_profile_list = False
                while not verified_wa_profile_list:
                    time.sleep(1)
                    verified_wa_profile_list = False
                    for object_store_obj in self.__get_indexed_db():
                        if 'WASecretBundle' in object_store_obj['key']:
                            verified_wa_profile_list = True
                            break
                self.log.debug('Login completed.')
        else:
            if self.__browser_choice == CHROME:
                options.add_argument('user-data-dir=%s' % os.path.join(self.__browser_user_dir, profile_name))
                self.__driver = webdriver.Chrome(options=options)
            elif self.__browser_choice == FIREFOX:
                fire_profile = webdriver.FirefoxProfile(os.path.join(self.__browser_user_dir, profile_name))
                self.__driver = webdriver.Firefox(fire_profile, options=options)

            self.log.debug('Loading WhatsApp Web...')
            self.__driver.get(self.__URL)

    def __start_visible_session(self, profile_name=None, wait_for_login=True):
        options = self.__browser_options
        options.headless = False
        self.__refresh_profile_list()

        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError('The specified profile_name was not found. Make sure the name is correct.')

        self.__start_session(options, profile_name, wait_for_login)

    def __start_invisible_session(self, profile_name=None):
        self.__refresh_profile_list()
        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError('The specified profile_name was not found. Make sure the name is correct.')

        self.__start_session(self.__browser_options, profile_name)

    def __init__(self, browser=None, log_level=None):
        self.log = logging.getLogger('WaWebSession:SessionHandler')
        log_format = logging.Formatter('%(asctime)s [%(levelname)s] (%(funcName)s): %(message)s')

        log_stream = logging.StreamHandler()
        log_stream.setLevel(logging.DEBUG)
        log_stream.setFormatter(log_format)
        self.log.addHandler(log_stream)

        if log_level is not None:
            self.set_log_level(log_level)
        else:
            self.__log_level = logging.WARNING
            self.log.setLevel(self.__log_level)

        self.__platform = platform.system().lower()
        if self.__platform != 'windows' and self.__platform != 'linux':
            raise OSError('Only Windows and Linux are supported for now.')
        self.log.debug('Detected platform: %s', self.__platform)

        self.__browser_choice = 0
        self.__browser_options = None
        self.__browser_user_dir = None
        self.__driver = None

        if browser:
            self.set_browser(browser)
        else:
            input_browser_choice = 0
            while input_browser_choice != 1 and input_browser_choice != 2:
                print('1) Chrome\n'
                      '2) Firefox\n')
                input_browser_choice = int(input('Select a browser by choosing a number from the list: '))
            if input_browser_choice == 1:
                self.set_browser(CHROME)
            elif input_browser_choice == 2:
                self.set_browser(FIREFOX)

        self.__init_browser()

    def set_log_level(self, new_log_level):
        possible_level_strings = ['debug', 'info', 'warning', 'error', 'critical']
        possible_level_values = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

        if type(new_log_level) == str:
            new_log_level = new_log_level.lower()
            if new_log_level in possible_level_strings:
                if new_log_level == possible_level_strings[0]:
                    self.__log_level = logging.DEBUG
                elif new_log_level == possible_level_strings[1]:
                    self.__log_level = logging.INFO
                elif new_log_level == possible_level_strings[2]:
                    self.__log_level = logging.WARNING
                elif new_log_level == possible_level_strings[3]:
                    self.__log_level = logging.ERROR
                elif new_log_level == possible_level_strings[4]:
                    self.__log_level = logging.CRITICAL
            else:
                raise ValueError('You can only use one of the following strings to change the log level: %s',
                                 str(possible_level_strings))
        else:
            if new_log_level in possible_level_values:
                self.__log_level = new_log_level
            else:
                raise ValueError(
                    'You can only pass a logging level or one of the following string to this function: %s',
                    str(possible_level_strings))

        self.log.setLevel(self.__log_level)

    def set_browser(self, browser):
        if type(browser) == str:
            if browser.lower() == 'chrome':
                self.log.debug('Setting browser... [TYPE: %s]', 'Chrome')
                self.__browser_choice = CHROME
            elif browser.lower() == 'firefox':
                self.log.debug('Setting browser... [TYPE: %s]', 'Firefox')
                self.__browser_choice = FIREFOX
            else:
                raise ValueError('The specified browser is invalid. Try to use "chrome" or "firefox" instead.')
        else:
            if browser == CHROME:
                self.log.debug('Setting browser... [TYPE: %s]', 'Chrome')
            elif browser == FIREFOX:
                self.log.debug('Setting browser... [TYPE: %s]', 'Firefox')
            else:
                raise ValueError(
                    'Browser type invalid. Try to use WaWebSession.CHROME or WaWebSession.FIREFOX instead.')

            self.__browser_choice = browser

    def get_active_session(self, use_profile=None):
        self.log.warning('Make sure the specified browser profile is not being used by another process.')
        profile_storage_dict = {}
        use_profile_list = []
        self.__refresh_profile_list()

        if use_profile and use_profile not in self.__browser_profile_list:
            raise ValueError('Profile does not exist: %s', use_profile)
        elif use_profile is None:
            return self.__get_profile_storage()
        elif use_profile and use_profile in self.__browser_profile_list:
            use_profile_list.append(use_profile)
        elif type(use_profile) == list:
            use_profile_list.extend(self.__browser_profile_list)
        else:
            raise ValueError("Invalid profile provided. Make sure you provided a list of profiles or a profile name.")

        for profile in use_profile_list:
            profile_storage_dict[profile] = self.__get_profile_storage(profile)

        return profile_storage_dict

    def create_new_session(self):
        return self.__get_profile_storage()

    def access_by_obj(self, wa_profile_list):
        verified_wa_profile_list = False
        for object_store_obj in wa_profile_list:
            if 'WASecretBundle' in object_store_obj['key']:
                verified_wa_profile_list = True
                break

        if not verified_wa_profile_list:
            raise ValueError('This is not a valid profile list. Make sure you only pass one session to this method.')

        self.__start_visible_session(wait_for_login=False)
        self.log.debug('Inserting setIDBObjects function...')
        self.__driver.execute_script('window.waScript = {};'
                                     'window.waScript.insertDone = 0;'
                                     'window.waScript.jsonObj = undefined;'
                                     'window.waScript.setAllObjects = function (_jsonObj) {'
                                     'window.waScript.jsonObj = _jsonObj;'
                                     'window.waScript.dbName = "wawc";'
                                     'window.waScript.osName = "user";'
                                     'window.waScript.db;'
                                     'window.waScript.transaction;'
                                     'window.waScript.objectStore;'
                                     'window.waScript.clearRequest;'
                                     'window.waScript.addRequest;'
                                     'window.waScript.request = indexedDB.open(window.waScript.dbName);'
                                     'window.waScript.request.onsuccess = function(event) {'
                                     'window.waScript.db = event.target.result;'
                                     'window.waScript.transaction = window.waScript.db.transaction('
                                     'window.waScript.osName, "readwrite");'
                                     'window.waScript.objectStore = window.waScript.transaction.objectStore('
                                     'window.waScript.osName);'
                                     'window.waScript.clearRequest = window.waScript.objectStore.clear();'
                                     'window.waScript.clearRequest.onsuccess = function(clearEvent) {'
                                     'for (var i=0; i<window.waScript.jsonObj.length; i++) {'
                                     'window.waScript.addRequest = window.waScript.objectStore.add('
                                     'window.waScript.jsonObj[i]);'
                                     'window.waScript.addRequest.onsuccess = function(addEvent) {'
                                     'window.waScript.insertDone++;'
                                     '};'
                                     '}'
                                     '};'
                                     '};'
                                     '}')
        self.log.debug('setIDBObjects function inserted.')
        self.log.debug('Writing IDB data: %s', wa_profile_list)
        self.__driver.execute_script('window.waScript.setAllObjects(arguments[0]);', wa_profile_list)

        self.log.debug('Waiting until all objects are written to IDB...')
        while not self.__driver.execute_script(
                'return (window.waScript.insertDone == window.waScript.jsonObj.length);'):
            time.sleep(1)

        self.log.debug('Reloading WhatsApp Web...')
        self.__driver.refresh()

        self.log.debug('Waiting until the browser window got closed...')
        while True:
            try:
                _ = self.__driver.window_handles
                time.sleep(1)
            except WebDriverException:
                break

    def access_by_file(self, profile_file):
        profile_file = os.path.normpath(profile_file)

        if os.path.isfile(profile_file):
            self.log.debug('Reading WaSession from file...')
            with open(profile_file, 'r') as file:
                wa_profile_list = json.load(file)

            self.log.debug('Verifying WaSession object...')
            verified_wa_profile_list = False
            for object_store_obj in wa_profile_list:
                if 'WASecretBundle' in object_store_obj['key']:
                    verified_wa_profile_list = True
                    break
            if verified_wa_profile_list:
                self.log.debug('WaSession object is valid.')
                self.access_by_obj(wa_profile_list)
            else:
                raise ValueError('There might be multiple profiles stored in this file.'
                                 ' Make sure you only pass one WaSession file to this method.')
        else:
            raise FileNotFoundError('Make sure you pass a valid WaSession file to this method.')

    def save_profile(self, wa_profile_list, file_path):
        file_path = os.path.normpath(file_path)

        verified_wa_profile_list = False
        for object_store_obj in wa_profile_list:
            if 'key' in object_store_obj:
                if 'WASecretBundle' in object_store_obj['key']:
                    verified_wa_profile_list = True
                    break
        if verified_wa_profile_list:
            self.log.debug('Saving WaSession object to file...')
            with open(file_path, 'w') as file:
                json.dump(wa_profile_list, file, indent=4)
        else:
            self.log.debug('Scanning the list for multiple WaSession objects...')
            saved_profiles = 0
            for profile_name in wa_profile_list.keys():
                profile_storage = wa_profile_list[profile_name]
                verified_wa_profile_list = False
                for object_store_obj in profile_storage:
                    if 'key' in object_store_obj:
                        if 'WASecretBundle' in object_store_obj['key']:
                            verified_wa_profile_list = True
                            break
                if verified_wa_profile_list:
                    self.log.debug('Found a new profile in the list!')
                    single_profile_name = os.path.basename(file_path) + '-' + profile_name
                    self.save_profile(profile_storage, os.path.join(os.path.dirname(file_path), single_profile_name))
                    saved_profiles += 1
            if saved_profiles > 0:
                self.log.debug('Saved %s profile objects as files.')
            else:
                raise ValueError(
                    'Could not find any profiles in the list. Make sure to specified file path is correct.')


if __name__ == '__main__':
    web = SessionHandler()
    web.set_log_level(logging.DEBUG)
    choice = 0
    while choice != 1 and choice != 2:
        print('1) Save session to file\n'
              '2) View session from a file\n')
        choice = int(input('Select an option from the list: '))

    if choice == 1:
        web.save_profile(web.get_active_session(), input('Enter a file path for the generated file: '))
        print('File saved.')
    elif choice == 2:
        web.access_by_file(input('Enter a file path: '))

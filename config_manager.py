import configparser

class ConfigurationManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()

    def load_config(self):
        self.config.read(self.config_file)

    def get_option(self, section, option):
        return self.config.get(section, option)

    def get_boolean_option(self, section, option):
        return self.config.getboolean(section, option)


    def set_option(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))

    def save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)
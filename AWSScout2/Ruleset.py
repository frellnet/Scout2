# Import future stuff...
from __future__ import print_function
from __future__ import unicode_literals


from opinel.utils import printException, printError, printInfo, printDebug, connect_service, manage_dictionary, read_ip_ranges
from AWSScout2.utils import recurse
from opinel.load_data import load_data
import json
import os
import re

finding_levels = ['danger', 'warning']

DEFAULT_RULESET = 'lol'

condition_operators = [ 'and', 'or' ]

# First search local under ./rules and ./rulesets
# Then search from package files
# Then error


re_ip_ranges_from_file = re.compile(r'_IP_RANGES_FROM_FILE_\((.*?),\s*(.*?)\)')
re_get_value_at = re.compile(r'_GET_VALUE_AT_\((.*?)\)')
re_list_value = re.compile(r'_LIST_\((.*?)\)')
aws_ip_ranges_filename = 'ip-ranges.json'
ip_ranges_from_args = 'ip-ranges-from-args'

FILTERS_DIR = 'filters'
RULES_DIR = 'rules'
RULESETS_DIR = 'rulesets'
DEFAULT_RULESET = '%s/default.json' % RULESETS_DIR


class Ruleset(object):
    """
    TODO
    """

    def __init__(self, environment_name = 'default', ruleset_filename = None, services = [], load_ruleset = True, load_rules = True):
        # Ruleset filename
        self.filename = ruleset_filename
        if not self.filename:
            self.search_ruleset(environment_name)
        # Load ruleset
        self.ruleset = {}
        if load_ruleset:
            self.load_ruleset()
        # Load rules
        self.rules = {}
        if load_rules:
            ip_ranges = {}
            aws_account_id = ''
            self.init_rules(services, ip_ranges, aws_account_id, False, 'rules')



    # Load findings from JSON config files
#    ruleset = load_ruleset(ruleset_filename)
#    rules = init_rules(ruleset, services, environment_name, args.ip_ranges, aws_config['account_id'])

    # Load filters from JSON config files
#    filters = load_ruleset('rulesets/filters.json')
#    filters = init_rules(filters, services, environment_name, args.ip_ranges, aws_config['account_id'],
 #                        rule_type='filters')


    def load_ruleset(self, quiet = False):
        if not self.filename or not os.path.exists(self.filename):
            if not quiet:
                printError('Error: the file %s does not exist.' % self.filename)
            return None
        try:
            with open(self.filename, 'rt') as f:
                self.ruleset = json.load(f)
        except Exception as e:
            printException(e)
            printError('Error: ruleset file %s contains malformed JSON.' % self.filename)
            return None


    def search_ruleset(self, environment_name):
        ruleset_found = False
        if environment_name != 'default':
            for f in os.listdir(os.getcwd()):
                if fnmatch.fnmatch(f, '*.' + environment_name + '.json'):
                    ruleset_found = True
            if ruleset_found and prompt_4_yes_no("A ruleset whose name matches your environment name was found in %s. Would you like to use it instead of the default one" % f):
                self.filename = f
        if not ruleset_found:
            self.filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/rulesets/default.json')
            printInfo(self.filename)
            printInfo('A')


            #load_data(sel, key_name=None, local_file=False):



    #
    # Initialize rules based on ruleset and services in scope
    #
    def init_rules(self, ruleset, services, ip_ranges, aws_account_id, generator = False, rule_type = 'rules'):
        ruleset_targets = getattr(self, rule_type)
        print(ruleset_targets)
        # Load rules from JSON files
        for rule_metadata in self.ruleset['rules']:
            # Skip disabled rules
            if 'enabled' in rule_metadata and rule_metadata['enabled'] in ['false', 'False', False] and not generator:
                continue
            # Skip rules that apply to an out-of-scope service
            rule_details = self.load_json_rule(rule_metadata, ip_ranges, aws_account_id, rule_type)
            if not rule_details:
                continue
            if 'enabled' in rule_metadata and rule_metadata['enabled']:
                rule_details['enabled'] = True
            skip_rule = True
            for service in services:
                if rule_details['path'].startswith(service):
                    skip_rule = False
#            if skip_rule:
#                continues
            #  Build the rules dictionary
            path = rule_details['path']
            if 'level' in rule_metadata:
                rule_details['level'] = rule_metadata['level']
            key = rule_details['key'] if 'key' in rule_details else rule_metadata['filename']
            # Set condition operator
            if not 'condition_operator' in rule_details:
                rule_details['condition_operator'] = 'and'
            # Save details for rule
            key = key.replace('.json', '').replace(' ', '')
            manage_dictionary(ruleset_targets, path, {})
            ruleset_targets[path][key] = rule_details





    #
    # Load rule from a JSON config file
    #
    def load_json_rule(self, rule_metadata, ip_ranges, aws_account_id, rule_type = 'rules'):
        config = None
        config_file = rule_metadata['filename']
        if not config_file.startswith('rules/') and not config_file.startswith('filters/'):
            config_file = '%s/%s' % (rule_type, config_file)
        config_args = rule_metadata['args'] if 'args' in rule_metadata else []
        try:
            with open(config_file, 'rt') as f:
                config = f.read()
            # Replace arguments
            for idx, argument in enumerate(config_args):
                config = config.replace('_ARG_'+str(idx)+'_', str(argument).strip())
            config = json.loads(config)
            config['filename'] = rule_metadata['filename']
            if 'args' in rule_metadata:
                config['args'] = rule_metadata['args']
            # Load lists from files
            for c1 in config['conditions']:
                if c1 in condition_operators:
                    continue
                if not type(c1[2]) == list and not type(c1[2]) == dict:
                    values = re_ip_ranges_from_file.match(c1[2])
                    if values:
                        filename = values.groups()[0]
                        conditions = json.loads(values.groups()[1])
                        if filename == aws_ip_ranges_filename:
                             c1[2] = read_ip_ranges(aws_ip_ranges_filename, False, conditions, True)
                        elif filename == ip_ranges_from_args:
                            c1[2] = []
                            for ip_range in ip_ranges:
                                c1[2] = c1[2] + read_ip_ranges(ip_range, True, conditions, True)
                    if c1[2] and aws_account_id:
                        if not type(c1[2]) == list:
                            c1[2] = c1[2].replace('_AWS_ACCOUNT_ID_', aws_account_id)
    
                    # Set lists
                    list_value = re_list_value.match(str(c1[2]))
                    if list_value:
                        values = []
                        for v in list_value.groups()[0].split(','):
                            values.append(v.strip())
                        c1[2] = values
        except Exception as e:
            printException(e)
            printError('Error: failed to read the rule from %s' % config_file)
        return config


    def analyze(self, aws_config):
        """

        :param aws_config:
        """
        printInfo('Analyzing AWS config...')
        for finding_path in self.rules:
            for rule in self.rules[finding_path]:
                printDebug('Processing %s rule: "%s"' % (finding_path.split('.')[0], self.rules[finding_path][rule]['description']))
                path = finding_path.split('.')
                service = path[0]
                manage_dictionary(aws_config['services'][service], 'violations', {})
                aws_config['services'][service]['violations'][rule] = {}
                aws_config['services'][service]['violations'][rule]['description'] = self.rules[finding_path][rule]['description']
                aws_config['services'][service]['violations'][rule]['path'] = self.rules[finding_path][rule]['path']
                aws_config['services'][service]['violations'][rule]['level'] = self.rules[finding_path][rule]['level']
                if 'id_suffix' in self.rules[finding_path][rule]:
                    aws_config['services'][service]['violations'][rule]['id_suffix'] = self.rules[finding_path][rule]['id_suffix']
                if 'display_path' in self.rules[finding_path][rule]:
                    aws_config['services'][service]['violations'][rule]['display_path'] = self.rules[finding_path][rule]['display_path']
                try:
                    aws_config['services'][service]['violations'][rule]['items'] = recurse(aws_config['services'], aws_config['services'], path, [], self.rules[finding_path][rule], True)
                    aws_config['services'][service]['violations'][rule]['dashboard_name'] = self.rules[finding_path][rule]['dashboard_name'] if 'dashboard_name' in self.rules[finding_path][rule] else '??'
                    aws_config['services'][service]['violations'][rule]['checked_items'] = self.rules[finding_path][rule]['checked_items'] if 'checked_items' in self.rules[finding_path][rule] else 0
                    aws_config['services'][service]['violations'][rule]['flagged_items'] = len(aws_config['services'][service]['violations'][rule]['items'])
                    aws_config['services'][service]['violations'][rule]['service'] = service
                except Exception as e:
                    printError('Failed to process rule defined in %s.json' % rule)
                    # Fallback if process rule failed to ensure report creation and data dump still happen
                    aws_config['services'][service]['violations'][rule]['checked_items'] = 0
                    aws_config['services'][service]['violations'][rule]['flagged_items'] = 0
                    printException(e)
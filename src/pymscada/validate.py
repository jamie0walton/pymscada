"""Config file validation."""
from cerberus import Validator
from yaml import dump
from pymscada import Config
from socket import inet_aton

INT_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['int']},
    'min': {'type': 'integer', 'required': False},
    'max': {'type': 'integer', 'required': False},
    'init': {'type': 'integer', 'required': False},
    'units': {'type': 'string', 'maxlength': 5, 'required': False},
    'format': {'type': 'string', 'allowed': ['date', 'time', 'datetime']}
}
FLOAT_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['float']},
    'min': {'type': 'float', 'required': False},
    'max': {'type': 'float', 'required': False},
    'init': {'type': 'float', 'required': False},
    'units': {'type': 'string', 'maxlength': 5, 'required': False},
    'dp': {'type': 'integer', 'min': 0, 'max': 6, 'required': False},
}
STR_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['str']},
    'init': {'type': 'string', 'required': False},
}
LIST_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['list']},
}
DICT_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['dict']},
    'init': {}
}
MULTI_TAG = {
    'desc': {'type': 'string'},
    'multi': {'type': 'list'},
    'init': {'type': 'integer', 'required': False},
}
BYTES_TAG = {
    'desc': {'type': 'string'},
    'type': {'type': 'string', 'allowed': ['bytes']},
}

TAG_SCHEMA = {
    'type': 'dict',
    'keysrules': {
        'type': 'string',
        # tag name discovery, save for later checking
        'ms_tagname': True
    },
    'valuesrules': {
        'type': 'dict',
        'oneof_schema': [
            INT_TAG, FLOAT_TAG, STR_TAG, LIST_TAG, DICT_TAG, MULTI_TAG,
            BYTES_TAG
        ],
        # tag type discovery, save for later checking
        'ms_tagtype': True
    },
}

BUS_SCHEMA = {
    'type': 'dict',
    'schema': {
        'ip': {'type': 'string', 'ms_ip': True},
        'port': {'type': 'integer', 'min': 1024, 'max': 65536}
    }
}

BRHR_LIST = {
    'type': {'type': 'string', 'allowed': ['br', 'hr']},
}
H123P_LIST = {
    'type': {
        'type': 'string',
        'allowed': ['h1', 'h2', 'h3', 'p'],
    },
    'desc': {'type': 'string'}
}
VALUESETFILES_LIST = {
    'type': {
        'type': 'string',
        'allowed': ['value', 'setpoint', 'files'],
    },
    # tagname must have been found in parsing tags.yaml
    'tagname': {'type': 'string', 'ms_tagname': False}
}
SELECTDICT_LIST = {
    'type': {'type': 'string', 'allowed': ['selectdict']},
    # tagname must have been found in parsing tags.yaml
    'tagname': {'type': 'string', 'ms_tagname': False},
    'opts': {
        'type': 'dict',
        # 'schema': {
        #     'type': 'dict',
        #     # 'schema': {
        #     #     'type': {'type': 'string', 'required': False},
        #     #     'multi': {'type': 'list', 'required': False},
        #     # }
        # },
        'required': False
    }
}
UPLOT_LIST = {
    'type': {'type': 'string', 'allowed': ['uplot']},
    'ms': {
        'type': 'dict',
        # 'schema': {
        #     'type': 'dict',
        #     # 'schema': {
        #     #     'type': {'type': 'string', 'required': False},
        #     #     'multi': {'type': 'list', 'required': False},
        #     # }
        # },
        'required': False
    },
    'axes': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'scale': {'type': 'string'},
                'range': {'type': 'list', 'items': [
                    {'type': 'float'}, {'type': 'float'}
                ]},
                'dp': {'type': 'integer', 'required': False}
            }
        }
    },
    'series': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                # tagname must have been found in parsing tags.yaml
                'tagname': {'type': 'string', 'ms_tagname': False},
                'label': {'type': 'string', 'required': False},
                'scale': {'type': 'string', 'required': False},
                'color': {'type': 'string', 'required': False},
                'width': {'type': 'float', 'required': False},
                'dp': {'type': 'integer', 'required': False},
            }
        }
    }
}

LIST_WWWSERVER = {
    'type': 'dict',
    'schema': {
        'name': {'type': 'string'},
        'parent': {'type': 'string', 'nullable': True},
        'items': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'oneof_schema': [
                    BRHR_LIST, H123P_LIST, VALUESETFILES_LIST,
                    SELECTDICT_LIST, UPLOT_LIST
                ]
            }
        },
    }
}

WWWSERVER_SCHEMA = {
    'type': 'dict',
    'schema': {
        'bus_ip': {'type': 'string', 'ms_ip': True},
        'bus_port': {'type': 'integer', 'min': 1024, 'max': 65536},
        'ip': {'type': 'string', 'ms_ip': True},
        'port': {'type': 'integer', 'min': 1024, 'max': 65536},
        'get_path': {'nullable': True},
        'paths': {'type': 'list', 'allowed': ['history', 'config', 'pdf']},
        'pages': {
            'type': 'list',
            'schema': LIST_WWWSERVER
        }
    }
}

HISTORY_SCHEMA = {
    'type': 'dict',
    'schema': {
        'bus_ip': {'type': 'string', 'ms_ip': True},
        'bus_port': {'type': 'integer', 'min': 1024, 'max': 65536},
        'path': {'type': 'string'},
    }
}

MODBUSSERVER_SCHEMA = {
    'type': 'dict',
    'schema': {
        'bus_ip': {'type': 'string', 'ms_ip': True, 'nullable': True},
        'bus_port': {'type': 'integer', 'min': 1024, 'max': 65536,
                     'nullable': True},
        'path': {'type': 'string'},
        'rtus': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'name': {},
                    'ip': {},
                    'port': {},
                    'tcp_udp': {'type': 'string', 'allowed': ['tcp', 'udp']},
                    'serve': {
                        'type': 'list',
                        'schema': {}
                    }
                }
            }
        },
        'tags': {
            'type': 'dict',
            'keysrules': {
                'type': 'string',
                'ms_tagname': False
            },
            'valuesrules': {
                'type': 'dict',
                'schema': {
                    'type': {},
                    'addr': {}
                },
            },
        },
    }
}

MODBUSCLIENT_SCHEMA = {
    'type': 'dict',
    'schema': {
        'bus_ip': {'type': 'string', 'ms_ip': True, 'nullable': True},
        'bus_port': {'type': 'integer', 'min': 1024, 'max': 65536,
                     'nullable': True},
        'path': {'type': 'string'},
        'rtus': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'name': {},
                    'ip': {},
                    'port': {},
                    'tcp_udp': {'type': 'string', 'allowed': ['tcp', 'udp']},
                    'rate': {},
                    'read': {
                        'type': 'list',
                        'schema': {}
                    },
                    'writeok': {
                        'type': 'list',
                        'schema': {}
                    }
                }
            }
        },
        'tags': {
            'type': 'dict',
            'keysrules': {
                'type': 'string',
                'ms_tagname': False
            },
            'valuesrules': {
                'type': 'dict',
                'schema': {
                    'type': {},
                    'addr': {}
                },
            }
        }           
    }
}

class MsValidator(Validator):
    """Add additional application checks"""
    ms_tagnames = {}

    def _validate_ms_tagname(self, constraint, field, value):
        """ Test tagname exists, capture when true.

        The rule's arguments are validated against this schema:
        {'type': 'boolean'}
        """
        if '.' in field:
            self._error(field, "'.' invalid in tag definition.")
        if constraint:
            if field in self.ms_tagnames:
                self._error(field, 'attempt to redefine')
            else:
                self.ms_tagnames[field] = {'type': None}
        else:
            if value not in self.ms_tagnames:
                self._error(field, 'tag was not defined in tags.yaml')
            else:
                pass

    def _validate_ms_tagtype(self, constraint, field, value):
        """ Test tagname type, capture when true.

        The rule's arguments are validated against this schema:
        {'type': 'boolean'}
        """
        if constraint and field in self.ms_tagnames:
            if self.ms_tagnames[field]['type'] is None:
                if 'multi' in value:
                    self.ms_tagnames[field]['type'] = 'int'
                else:
                    self.ms_tagnames[field]['type'] = value['type']
            else:
                self._error(field, 'attempt to redefine type')
        else:
            pass

    def _validate_ms_ip(self, constraint, field, value):
        """ Test session.inet_aton works for the address.

        The rule's arguments are validated against this schema:
        {'type': 'boolean'}
        """
        try:
            inet_aton(value)
        except (OSError, TypeError):
            self._error(field, 'ip address fails socket.inet_aton')


def validate(path: str=''):
    """Validate."""
    s = {
        'tags': TAG_SCHEMA,
        'bus': BUS_SCHEMA,
        'wwwserver': WWWSERVER_SCHEMA,
        'history': HISTORY_SCHEMA,
        'modbusserver': MODBUSSERVER_SCHEMA,
        'modbusclient': MODBUSCLIENT_SCHEMA,
    }
    c = {
        'tags': dict(Config(f'{path}/tags.yaml')),
        'bus': dict(Config(f'{path}/bus.yaml')),
        'wwwserver': dict(Config(f'{path}/wwwserver.yaml')),
        'history': dict(Config(f'{path}/history.yaml')),
        'modbusserver': dict(Config(f'{path}/modbusserver.yaml')),
        'modbusclient': dict(Config(f'{path}/modbusclient.yaml')),
    }
    v = MsValidator(s)
    res = v.validate(c)
    wdy = dump(v.errors)  # , default_flow_style=False)
    return res, wdy
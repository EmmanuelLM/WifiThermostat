"""
Support for Chinese wifi thermostats (Floureon, Beok, Beca Energy)

configuration.yaml
climate:
  - platform: wifithermostat
    api_key: xxxxx
"""

import socket, logging, binascii


_LOGGER = logging.getLogger(__name__)


from homeassistant.components.climate import (ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_ON_OFF)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.helpers.discovery import load_platform

DOMAIN = 'wifithermostat'
REQUIREMENTS = []
DEPENDENCIES = []

class decode_payload:
    def __init__(self, payload):
        self.payload = payload
        #print self.payload

    def get_command(self):
        #return ((self.payload >> 56) & 255)
        return self.payload[:2]

    def get_id0(self):
        #return ((self.payload >> 48) & 255)
        return self.payload[2:4]

    def get_id1(self):
        #return ((self.payload >> 40) & 255)
        return self.payload[4:6]

    def get_data0(self):
        #return ((self.payload >> 32) & 255)
        return self.payload[6:8]

    def get_data1(self):
        #return ((self.payload >> 24) & 255)
        return self.payload[8:10]

    def get_data2(self):
        #return ((self.payload >> 16) & 255)
        return int(self.payload[10:12],16)

    def get_data3(self):
        #return ((self.payload >> 8) & 255)
        return int(self.payload[12:14],16)

    def get_checksum(self):
        #return ((self.payload >> 0) & 255)
        return self.payload[14:16]


class wifi_thermostat:
    def __init__(self, PID, name):
        self.id_effect = (PID+1)*65535+65535
        self.HOST = '59.110.30.249'
        self.PORT = 25565
        self.current_temp = None
        self.mode = 'auto'
        self.power = 'off'
        self.setpoint = None
        self.name = name

    def data_package(self, Command, ID0, ID1, Data0, Data1, Data2, Data3):
        self.Command = int(Command, 0)
        self.ID0 = int(ID0, 0)
        self.ID1 = int(ID1, 0)
        self.Data0 = int(Data0, 0)
        self.Data1 = int(Data1, 0)
        self.Data2 = int(Data2, 0)
        self.Data3 = int(Data3, 0)
        self.checksum = checksum = (self.Command + self.ID0 + self.ID1 + self.Data0 + self.Data1 + self.Data2 + self.Data3) & 0xFF ^ 0xA5
        self.output = "0xFFFFFFFFFFFFFFFF"
        self.output = (self.Command << 56) | (self.ID0 << 48) | (self.ID1 << 40) | (self.Data0 << 32) | (self.Data1 << 24) | (self.Data2 << 16) | (self.Data3 << 8) | self.checksum
        return self.output

    def poweronoff(self, power):
        self.power = power
        if self.power == "on":
            powerdata = "0x30"
        elif self.power == "off":
            powerdata = "0x00"
        payload = self.data_package("0xA2", "0x01", "0x01", powerdata, "0x00", "0x00", "0x00")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.HOST, self.PORT))
            data = bytearray.fromhex(hex(self.id_effect)[2:])
            s.send(data)
            temp = hex(payload)[2:].rstrip("L")
            data = bytearray.fromhex(temp)
            s.send(data)
            s.close
        except socket.error as err:
            _LOGGER.error("Could not power on or off")

    def set_temperature(self, temperature):
        self.setpoint = str(2*int(temperature))
        payload = self.data_package("0xA6", "0x01", "0x01", "0x00", "0x00", self.setpoint, "0x00")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.HOST, self.PORT))
            data = bytearray.fromhex(hex(self.id_effect)[2:])
            s.send(data)
            temp = hex(payload)[2:].rstrip("L")
            data = bytearray.fromhex(temp)
            s.send(data)
            s.close
        except socket.error as err:
            _LOGGER.error("Could not set temperature")

    def read_status(self):
        payload = self.data_package("0xA0", "0x01", "0x01", "0x00", "0x00", "0x00", "0x00")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.HOST, self.PORT))
            s.settimeout(10)
            data = bytearray.fromhex(hex(self.id_effect)[2:])
            s.send(data)
            temp = hex(payload)[2:].rstrip("L")
            data = bytearray.fromhex(temp)
            s.send(data)
            s.close
        except socket.error as err:
            _LOGGER.error("Could not read status")
        
#        data2 = s.recv(64).encode("hex")
        data2 = binascii.hexlify(s.recv(64))
        b = decode_payload(data2)

        self.current_temp = float(b.get_data3()) / 2
        self.setpoint = float(b.get_data2()) / 2
        
        self.status = b.get_data0()
        if self.status == 28:
            self.mode = 'manual'
            self.power = 'off'
        elif self.status == 38:
            self.mode = 'manual'
            self.power = 'on'
        elif self.status == 20:
            self.mode = 'auto'
            self.power = 'off'
        else:
            self.mode = 'auto'
            self.power = 'on'
        
            

#-----------------------------------------------------------------------------------------------------------



class WifiThermostat(ClimateDevice):

    def __init__(self, hass, device):
        self._device = device
        self._hass = hass

    @property
    def supported_features(self):
        return (SUPPORT_TARGET_TEMPERATURE | SUPPORT_ON_OFF)

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._device.name

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS
    
    @property
    def min_temp(self):
        return 5
    
    @property
    def max_temp(self):
        return 35

    @property
    def current_temperature(self):
        self._device.read_status()
        return self._device.current_temp

    @property
    def target_temperature(self):
        self._device.read_status()
        return self._device.setpoint

    @property
    def is_on(self):
        if self._device.power == "on":
            return True
        else:
            return False

    def set_temperature(self, **kwargs):
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))
                    

    def turn_on(self):
        self._device.poweronoff("on")


    def turn_off(self):
        self._device.poweronoff("off")


    def update(self):
        self._device.read_status()


# ---------------------------------------------------------------

def setup_platform(hass, config, add_devices, discovery_info=None):
    _LOGGER.debug("Adding component: wifi_thermostat ...")
	
    api_key = config.get("api_key")
    name = config.get("name")

        
    if api_key is None:
        _LOGGER.error("Wifi Thermostat: Invalid API KEY !")
        return False
    
    if name is None:
        _LOGGER.error("Wifi Thermostat: Invalid name !")
        return False

    wt = wifi_thermostat(api_key, name)
	
    add_devices([WifiThermostat(hass, wt), True])
	
    _LOGGER.debug("Wifi Thermostat: Component successfully added !")
    return True

# ---------------------------------------------------------------
import socket
from netifaces import interfaces, ifaddresses
from platform import system


class IpAddrOrHostname:
    def __init__(self):
        self.ip_addr = 'DESCONHECIDO'
        self.host_name = 'DESCONHECIDO'

    @property
    def ip_addr_or_hostname(self):
        """ Retorna uma lista com ip e hostname do host"""
        try:
            if system() == 'Darwin':
                self.ip_addr = ifaddresses(interfaces()[18])[2][0]['addr']
                self.host_name = socket.gethostname()
            elif system() == 'Linux':
                self.ip_addr = ifaddresses(interfaces()[1])[2][0]['addr']
                self.host_name = socket.gethostname()
            elif system() == 'Windows':
                pass
        except socket.error as err:
            return err

        return [self.ip_addr, self.host_name]

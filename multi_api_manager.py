""" Manage multiple apis at once - allows calculating better values by
incorporating multiple sources. """

import logging
from weighted_average import WeightedAverage


class MultiApiManager():
    def __init__(self, api_obj_list):
        self.api_obj_list = api_obj_list
    
    def update(self):
        for api_obj in self.api_obj_list:
            try:
                api_obj.update()
                logging.debug('updated {} successfully'.format(api_obj.api_name))
            except:
                logging.exception('Unhandled Exception updating {}'.format(api_obj.api_name))

    def price_eth(self, currency_symbol='0xBTC', api_name='all'):
        result = WeightedAverage()
        for a in self.api_obj_list:
            if a.currency_symbol != currency_symbol:
                continue
            if a.price_eth == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result.add(a.price_eth, a.volume_eth)
        return result.average()

    def price_usd(self, currency_symbol='0xBTC', api_name='all'):
        result = WeightedAverage()
        for a in self.api_obj_list:
            if a.currency_symbol != currency_symbol:
                continue
            if a.price_usd == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result.add(a.price_usd, a.volume_eth)
        return result.average()

    def volume_usd(self, currency_symbol='0xBTC', api_name='all'):
        result = 0
        for a in self.api_obj_list:
            if a.currency_symbol != currency_symbol:
                continue
            if a.volume_usd == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result += a.volume_usd
        return result

    def volume_eth(self, currency_symbol='0xBTC', api_name='all'):
        result = 0
        for a in self.api_obj_list:
            if a.currency_symbol != currency_symbol:
                continue
            if a.volume_eth == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result += a.volume_eth
        return result

    def change_24h(self, currency_symbol='0xBTC', api_name='all'):
        result = WeightedAverage()
        for a in self.api_obj_list:
            if a.currency_symbol != currency_symbol:
                continue
            if a.change_24h == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result.add(a.change_24h, a.volume_eth)
        return result.average()

    def eth_price_usd(self, api_name='all'):
        result = WeightedAverage()
        for a in self.api_obj_list:
            if a.eth_price_usd == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result.add(a.eth_price_usd, a.volume_eth)
        return result.average()

    def btc_price_usd(self, api_name='all'):
        result = WeightedAverage()
        for a in self.api_obj_list:
            if a.btc_price_usd == None:
                continue
            if api_name == 'all' or a.api_name == api_name:
                result.add(a.btc_price_usd, a.volume_eth)
        return result.average()

    def last_updated_time(self, api_name='all'):
        result = 0
        for a in self.api_obj_list:
            if a.last_updated_time == None or a.last_updated_time == 0:
                continue
            if api_name == 'all' or a.api_name == api_name:
                # use the lowest last_updated time
                if result == 0 or a.last_updated_time < result:
                    result = a.last_updated_time
        return result

if __name__ == "__main__":
    from enclavesdex import EnclavesAPI
    from livecoinwatch import LiveCoinWatchAPI

    apis = [
        EnclavesAPI('0xBTC'), 
        LiveCoinWatchAPI('0xBTC'),
        LiveCoinWatchAPI('ETH'),
    ]

    m = MultiApiManager(apis)
    m.update()

    print("m.price_eth", m.price_eth())
    print("m.price_usd", m.price_usd())
    print("m.volume_usd", m.volume_usd())
    print("m.volume_eth", m.volume_eth())
    print("m.change_24h", m.change_24h())
    print("m.eth_price_usd", m.eth_price_usd())
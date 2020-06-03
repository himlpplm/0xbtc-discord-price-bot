"""
API for Uniswap v2 distributed exchange (uniswap.exchange)
Price info is pulled from the smart contract
"""
import logging
from web3 import Web3
import time

from .base_exchange import BaseExchangeAPI
from .uniswap_v2_abi import exchange_abi
from .uniswap_v2_router_abi import router_abi
from secret_info import ETHEREUM_NODE_URL
from constants import SECONDS_PER_ETH_BLOCK

# location of uniswap v2 router countract (shouldn't need to change this unless the
# router is upgraded)
router_address = "0xf164fC0Ec4E93095b804a4795bBe1e041497b92a"

# list of tokens used by this module
# token name, token address, token decimals
tokens = (
("SHUF", "0x3A9FfF453d50D4Ac52A6890647b823379ba36B9E", 18),
("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
("USDC", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6),
("0xBTC", "0xB6eD7644C69416d67B522e20bC294A9a9B405B31", 8),
("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18),
("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),

)

def getTokenAddressFromName(name):
    return [i[1] for i in tokens if i[0] == name][0]
def getTokenNameFromAddress(address):
    return [i[0] for i in tokens if i[1].lower() == address.lower()][0]
def getTokenDecimalsFromName(name):
    return [i[2] for i in tokens if i[0] == name][0]
def getTokenDecimalsFromAddress(address):
    return [i[2] for i in tokens if i[1].lower() == address.lower()][0]

# list of exchange contract addresses for uniswap v2. each pair has a unique address.
# token0 name, token1 name, uniswap exchange address
exchanges = (
("0xBTC", "WETH", "0xc12c4c3E0008B838F75189BFb39283467cf6e5b3"),
("DAI", "0xBTC", "0x095739e9Ea7B0d11CeE1c1134FB76549B610f4F3"),
("USDC", "0xBTC", "0xA99F7Bc92c932A2533909633AB19cD7F04805059"),
("SHUF", "0xBTC", "0x1f9119d778d0B631f9B3b8974010ea2B750e4d33"),
("DAI", "WETH", "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"),
("USDC", "WETH", "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"),
("DAI", "USDT", "0xB20bd5D04BE54f870D5C0d3cA85d82b34B836405"),
("DAI", "USDC", "0xAE461cA67B15dc8dc81CE7615e0320dA1A9aB8D5"),
("WETH", "USDT", "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852"),
("USDC", "WETH", "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"),
)

def getExchangeAddressesForToken(name):
    return [i[2] for i in exchanges if i[0].lower() == name.lower() or i[1].lower() == name.lower()]
def getTokensFromExchangeAddress(exchange_address):
    return [(i[0], i[1]) for i in exchanges if i[2].lower() == exchange_address.lower()][0]
def getExchangeAddressForTokenPair(first_token_name, second_token_name):
    token_addresses = sorted([getTokenAddressFromName(first_token_name).lower(), getTokenAddressFromName(second_token_name).lower()])
    for token1_name, token2_name, address in exchanges:
        if (token1_name in [first_token_name, second_token_name]
            and token2_name in [first_token_name, second_token_name]):
            return address, getTokenNameFromAddress(token_addresses[0]), getTokenNameFromAddress(token_addresses[1])
    return None

def wei_to_ether(amount_in_wei):
    return int(amount_in_wei) / 1000000000000000000.0

def ether_to_wei(amount_in_ether):
    return int(amount_in_ether * 1000000000000000000.0)

# HACK
# python implementation of uniswap router contract's getAmountOut function. Once web3.py
# supports solidity >= 0.6, we should be able to use the real getAmountOut function.
#
#     function getAmountOut(uint amountIn, uint reserveIn, uint reserveOut) internal pure returns (uint amountOut) {
#         require(amountIn > 0, 'UniswapV2Library: INSUFFICIENT_INPUT_AMOUNT');
#         require(reserveIn > 0 && reserveOut > 0, 'UniswapV2Library: INSUFFICIENT_LIQUIDITY');
#         uint amountInWithFee = amountIn.mul(997);
#         uint numerator = amountInWithFee.mul(reserveOut);
#         uint denominator = reserveIn.mul(1000).add(amountInWithFee);
#         amountOut = numerator / denominator;
#     }
def get_amount_out__uniswap_router(amountIn, reserveIn, reserveOut):
    amountIn = int(amountIn)
    reserveIn = int(reserveIn)
    reserveOut = int(reserveOut)
    if amountIn <= 0 or reserveIn <= 0 or reserveOut <= 0:
        return None
    amountInWithFee = amountIn * 997
    numerator = amountInWithFee * reserveOut
    denominator = (reserveIn * 1000) + amountInWithFee
    return numerator / denominator



class Uniswapv2API(BaseExchangeAPI):
    def __init__(self, currency_symbol):
        super().__init__()
        try:
            self._exchange_addresses = getExchangeAddressesForToken(currency_symbol)
            self._decimals = getTokenDecimalsFromName(currency_symbol)
        except IndexError:
            raise RuntimeError("Unknown currency_symbol {}, need to add address to uniswap_v2.py".format(currency_symbol))

        self.currency_symbol = currency_symbol
        self.exchange_name = "Uniswap v2"
        self.command_names = ["uniswap"]
        self.short_url = "https://bit.ly/35nae4n"  # main uniswap pre-selected to 0xbtc
        self.volume_eth = 0

        self._time_volume_last_updated = 0

        self._w3 = Web3(Web3.HTTPProvider(ETHEREUM_NODE_URL))
        self._exchanges = [self._w3.eth.contract(address=a, abi=exchange_abi) for a in self._exchange_addresses]
        #self._router = self._w3.eth.contract(address=router_address, abi=router_abi)

    async def _get_volume_at_exchange_contract(self, exchange_contract, timeout=10.0):
        volume_tokens = 0

        swap_topic = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
        sync_topic = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"
        burn_topic = "0xdccd412f0b1252819cb1fd330b93224ca42612892bb3f4f789976e6d81936496"
        transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        approval_topic = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
        mint_topic = "0x4c209b5fc8ad50758f13e2e1088ba56a560dff690a1c6fef26394f4c03821c4f"

        token0_address = exchange_contract.functions.token0().call()
        token1_address = exchange_contract.functions.token1().call()
        # print('token0_address:', token0_address)
        # print('token1_address:', token1_address)

        current_eth_block = self._w3.eth.blockNumber
        
        for event in self._w3.eth.getLogs({
                'fromBlock': current_eth_block - (int(60*60*24 / SECONDS_PER_ETH_BLOCK)),
                'toBlock': current_eth_block - 1,
                'address': exchange_contract.address}):
            topic0 = self._w3.toHex(event['topics'][0])
            if topic0 == swap_topic:
                print('swap')
                receipt = self._w3.eth.getTransactionReceipt(event['transactionHash'])
                parsed_log = exchange_contract.events.Swap().processReceipt(receipt)[0]
                #sender_address = parsed_log.args.sender
                #to_address = parsed_log.args.to
                amount0In = parsed_log.args.amount0In
                amount1In = parsed_log.args.amount1In
                amount0Out = parsed_log.args.amount0Out
                amount1Out = parsed_log.args.amount1Out
                #block_number = parsed_log.blockNumber

                if getTokenNameFromAddress(token0_address) == self.currency_symbol:
                    # token0 is the tracked currency symbol
                    volume_tokens += abs((amount0In - amount0Out) / 10**getTokenDecimalsFromAddress(token0_address))
                elif getTokenNameFromAddress(token1_address) == self.currency_symbol:
                    # token1 is the tracked currency symbol
                    volume_tokens += abs((amount1In - amount1Out) / 10**getTokenDecimalsFromAddress(token1_address))

                # if (amount0In - amount0Out) > 0 and (amount1In - amount1Out) < 0:
                #     # user trades token0 for token1
                #     pass
                # elif (amount0In - amount0Out) < 0 and (amount1In - amount1Out) > 0:
                #     # user trades token1 for token0
                #     pass
                # else:
                #     logging.debug('trade with some weird numbers... txhash={}'.format(self._w3.toHex(event['transactionHash'])))
                #     logging.debug('amount0In:'.format(amount0In))
                #     logging.debug('amount1In:'.format(amount1In))
                #     logging.debug('amount0Out:'.format(amount0Out))
                #     logging.debug('amount1Out:'.format(amount1Out))
                #     continue

                print('    token', token0_address, 'send to exchange', (amount0In - amount0Out) / 10**getTokenDecimalsFromAddress(token0_address), getTokenNameFromAddress(token0_address))
                print('    token', token1_address, 'send to exchange', (amount1In - amount1Out) / 10**getTokenDecimalsFromAddress(token1_address), getTokenNameFromAddress(token1_address))

                continue

            elif topic0 == sync_topic:
                # skip liquidity deposits/withdrawals
                continue
            elif topic0 == burn_topic:
                # skip liquidity deposits/withdrawals
                continue
            elif topic0 == transfer_topic:
                # skip liquidity deposits/withdrawals
                continue
            elif topic0 == approval_topic:
                # skip liquidity deposits/withdrawals
                continue
            elif topic0 == mint_topic:
                # skip liquidity deposits/withdrawals
                continue
            else:
                logging.debug('unknown topic txhash {}'.format(self._w3.toHex(event['transactionHash'])))
                logging.debug('unknown topic topic0 {}'.format(topic0))

        return volume_tokens

    async def _update_24h_volume(self, timeout=10.0):
        self.volume_tokens = 0
        for exchange_contract in self._exchanges:
            self.volume_tokens += await self._get_volume_at_exchange_contract(exchange_contract)

        self._time_volume_last_updated = time.time()

    async def _update(self, timeout=10.0):
        self.price_eth = self.get_price("WETH", self.currency_symbol)
        self.liquidity_eth = self.get_reserves("WETH", self.currency_symbol)[0]

        eth_prices = [
            self.get_price("DAI", "WETH"),
            self.get_price("USDT", "WETH"),
            self.get_price("USDC", "WETH"),
        ]
        # TODO: weighted average would be better than a simple average
        self.eth_price_usd = sum(eth_prices) / len(eth_prices)
        self.btc_price_usd = None

        # update volume once every hour since it (potentially) loads eth api
        if time.time() - self._time_volume_last_updated > 60*60:
            await self._update_24h_volume()

    # returns the number of token1 tokens you can buy for a given number of token0 tokens
    def get_swap_amount(self, amount, token0_name, token1_name):
        exchange_address, first_token_name, second_token_name = getExchangeAddressForTokenPair(token0_name, token1_name)
        exchange = self._w3.eth.contract(address=exchange_address, abi=exchange_abi)
        reserves = exchange.functions.getReserves().call()
        if token0_name == second_token_name:
            reserves[0], reserves[1] = reserves[1], reserves[0]

        token0_decimals = getTokenDecimalsFromName(token0_name)
        token1_decimals = getTokenDecimalsFromName(token1_name)

        # TODO: swap this for the real function (commented below) once web3.py
        # supports solidity >= 0.6
        amount_out = get_amount_out__uniswap_router(
            amount * 10**token0_decimals,
            reserves[0],
            reserves[1])
        # amount_out = self._router.functions.getAmountOut(
        #     amount * 10**token0_decimals, 
        #     reserves[0], 
        #     reserves[1]).call()
        return amount_out / 10**token1_decimals

    # returns the number of token1 tokens you can buy for a given number of token0 tokens
    def get_reserves(self, token0_name, token1_name):
        token0_decimals = getTokenDecimalsFromName(token0_name)
        token1_decimals = getTokenDecimalsFromName(token1_name)
        exchange_address, first_token_name, second_token_name = getExchangeAddressForTokenPair(token0_name, token1_name)
        exchange = self._w3.eth.contract(address=exchange_address, abi=exchange_abi)
        reserves = exchange.functions.getReserves().call()
        reserves[0] = reserves[0] / 10**getTokenDecimalsFromName(first_token_name)
        reserves[1] = reserves[1] / 10**getTokenDecimalsFromName(second_token_name)

        if token0_name == second_token_name:
            reserves[0], reserves[1] = reserves[1], reserves[0]

        return reserves[0], reserves[1]

    def get_price(self, token0_name, token1_name):
        reserves = self.get_reserves(token0_name, token1_name)
        return reserves[0] / reserves[1]


if __name__ == "__main__":
    e = Uniswapv2API('0xBTC')
    print('$1 in USDC will swap for {} 0xBTC tokens'.format(e.get_swap_amount(1, "USDC", "0xBTC")))
    print('$1 in DAI will swap for {} 0xBTC tokens'.format(e.get_swap_amount(1, "DAI", "0xBTC")))
    print('1 0xBTC token will swap for {} DAI'.format(e.get_swap_amount(1, "0xBTC", "DAI")))
    print('100 0xBTC tokens will swap for {} DAI'.format(e.get_swap_amount(100, "0xBTC", "DAI")))
    print('1 ETH will swap for {} DAI'.format(e.get_swap_amount(1, "WETH", "DAI")))
    print('230 DAI will swap for {} ETH'.format(e.get_swap_amount(230, "DAI", "WETH")))
    print('0xbtc and ETH balances:', e.get_reserves("0xBTC", "WETH"))
    print('0xbtc and ETH price:', e.get_price("0xBTC", "WETH"), "0xBTC per ETH")
    print('0xbtc and ETH price:', e.get_price("WETH", "0xBTC"), "ETH per 0xBTC")
    print()
    print('eth usdc reserves ', e.get_reserves("WETH", "USDC"))
    print('1 in ETH will swap for {} USDC '.format(e.get_swap_amount(1, "WETH", "USDC")))
    print('1 in ETH will swap for {} USDT '.format(e.get_swap_amount(1, "WETH", "USDT")))
    print('1 in ETH will swap for {} DAI '.format(e.get_swap_amount(1, "WETH", "DAI")))
    print()
    e.load_once_and_print_values()
    print()
    print('0xbtc-weth liquidity in eth', e.liquidity_eth)
    # e = Uniswapv2API('DAI')
    # e.load_once_and_print_values()

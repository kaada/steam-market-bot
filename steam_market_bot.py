#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
steam_market_bot.py
Olav Kaada, 2012

High-frequency trading of items on the Steam Community Market (http://steamcommunity.com/market/),
a market for virtual items made for the Steam platform.

splinter is needed for the software to run, and can be downloaded at: https://pypi.python.org/pypi/splinter,
or by using the command 'pip install splinter.'

Other files needed:
mail_self.py
mail-template.txt

UPDATE: No longer puts items back into the market (at market price) automatically. The market (server-side) is under constant developement, and the risk of failure is therefore too high.

UPDATE 2: This program is no longer under active developement, and is for this reason out-of-date. It is most likely still functional, but use with great care.
"""

import sys
import random
import httplib2
import socket
import time
from time import sleep, localtime, strftime
import datetime
from splinter import Browser
import mail_self

MARKET_BASE_URL = 'http://steamcommunity.com/market/'
MIN_SLEEP_TIME_IN_SECONDS = 3 # Please be a 'good' internet citizen

class Item:
    """Each item the bot is targeting is an object of this class."""

    def __init__(self, name, percent_off_to_buy=75):
        """Initialize a new Item object.

        Keyword arguments:
        name -- the name of the item, in clear text.
        percent_off_to_buy -- Minimum percent off the normal price, before the bot purchases the item."""

        self.name = name
        self.percent_off_to_buy = percent_off_to_buy

    def update_price(self, http):
        """Updates the price of an item, according to the new prices on the website. This should be done frequently to prevent prices from being out-of-date.

        Keyword arguments:
        http -- An httplib2.Http() object."""

        offers = None
        for x in xrange(0, 3):
            p = get_page_source(http, self.name)
            if not p:
                print 'No connection. {0} try left.'.format(2-x)
                if x != 2:
                    rand_sleep(MIN_SLEEP_TIME_IN_SECONDS)
            else:
                offers = fetch_item_offers(p, self.name)
                if offers:
                    break
                else:
                    print 'No data was found. {0} try left.'.format(2-x) # Occasionally the offer-data delivered within the HTML is empty, due to server overload.
                    if x != 2:
                        rand_sleep(MIN_SLEEP_TIME_IN_SECONDS)

        if offers is None or len(offers) < 2:
            self.average_price = 0.001
            print 'ERROR: NO VALUE KNOWN FOR THE AVERAGE PRICE OF {0}. AVERAGE PRICE SET TO 0.001 EURO.'.format(self.name.upper())
            print '{0} - new price: {1} euro'.format(self.name, self.average_price)
        else:
            self.average_price = average_price(offers)
            print '{0} - new price: {1} euro'.format(self.name, self.average_price)

class Market_bot():
    """Handling the top-level cycle. Includes the class-sprecific methods and objects."""

    items = None

    http = None
    browser = None

    start_date = None
    start_time = 0
    loops = 0
    items_found = 0
    highest_percent_cheaper_found = 0
    items_found_data = []

    G_SESSIONID = None

    def __init__(self):
        """Initializes the objects, including the list of items to be traded."""

        socket.setdefaulttimeout(5) # Setting the global socket timeout to 5 sec. This is done to prevent the program from getting stuck while waiting for a http response.

        # Declaring some random items. Should be moved to another file, but cba.
        self.items = (Item('Treasure Key', 30),
                 Item('Golden Greevil', 30),
                 Item('Vintage Timebreaker', 30),
                 Item('Dragonclaw Hook', 30),
                 Item('Unusual Lockjaw the Boxhound', 50),
                 Item('Unusual Drodo the Druffin', 50),
                 Item("Genuine Berserker's Witchslayer", 50),
                 Item('Genuine Kantusa the Script Sword', 50),
                 Item('Genuine Bow of the Howling Wind', 50),
                 Item('Genuine Wyvernguard Edge', 50),
                 Item('Genuine Recluse Reef Denizen', 50),
                 Item('Genuine Braze the Zonkey', 50),
                 Item('Genuine Dolfrat and Roshinante', 50),
                 Item('Genuine Ramnaught of Underwool'))

        self.http = httplib2.Http()
        self.browser = self.init_browser()
        print 'Please log in to your steam account.'
        self.G_SESSIONID = raw_input('g_sessionID: ')

        self.start_date = strftime("%a, %d %b %Y %X", localtime())
        self.start_time = time.time()

    def run(self):
        """The program flow. This method starts the process after the initializing is done.

        The program runs until stopped by the user.
        The prices are updated every 1500 loop, i.e. every ~1.5h.
        A status mail is sent to the default email every ~3h."""

        for item in self.items:
            print 'Name: {0}, percent off to buy: {1}%'.format(item.name, item.percent_off_to_buy)
        print 'Sleep time: {0}s - {1}s'.format(MIN_SLEEP_TIME_IN_SECONDS, MIN_SLEEP_TIME_IN_SECONDS+1)
        print '-----'

        while True:
            if self.loops % 1500 == 0:
                print 'UPDATING PRICES\n-----'
                self.update_prices()
                print 'PRICES ARE UPDATED\n-----'

                if (self.loops != 0) and (self.loops % 3000 == 0):
                    self.send_status_mail()
                    self.highest_percent_cheaper_found = 0
                    del self.items_found_data[:]

            p = get_page_source(self.http, None)
            time_check_start = datetime.datetime.now()

            if not p:
                print 'No connection'
                rand_sleep(MIN_SLEEP_TIME_IN_SECONDS)
                continue

            offers = fetch_item_offers(p, None)
            print 'DotA2 items listed: {0}'.format(len(offers))

            for offer in offers:
                for i in self.items:
                    if offer['item_name'] == i.name:
                        print '> {0}, {1} euro'.format(offer['item_name'], offer['price'])
                        percent_off = self.percent_cheaper(offer)
                        print "{0:.2f}% off (avg. price: {1}, percent off to buy: {2})".format(percent_off, i.average_price, i.percent_off_to_buy)

                        if percent_off >= i.percent_off_to_buy:
                            print 'FOUND <{0}> FOR {1} EURO'.format(offer['item_name'].upper(), offer['price'])
                            self.buy(offer['id'], self.fetch_buy_info(p, offer['id']), time_check_start)
                            self.items_found_data.append([offer['item_name'], offer['price'], percent_off, offer['seller']])
                            self.items_found = self.items_found + 1

                        if self.highest_percent_cheaper_found < percent_off:
                            self.highest_percent_cheaper_found = percent_off

            self.loops = self.loops + 1
            print 'loops: {0}\nhighest_percent_cheaper_found: {1:.2f}\nitems_found: {2}'.format(self.loops, self.highest_percent_cheaper_found, self.items_found)
            rand_sleep(MIN_SLEEP_TIME_IN_SECONDS)

    def update_prices(self):
        for item in self.items:
            item.update_price(self.http)
            rand_sleep(MIN_SLEEP_TIME_IN_SECONDS)

    def percent_cheaper(self, offer):
        """Returns the difference between the price of the object handed to the method, and the normal price of that given item.

        Keyword arguments:
        offer -- The new offer for the method to calculate the percent-off for."""

        for i in self.items:
            if offer['item_name'] == i.name:
                offer_price = offer['price']
                return (1 - offer_price / i.average_price)*100

    def fetch_buy_info(self, page_html, listingid):
        """Returning the info needed to perform the transaction.
        Parcing HTML is BAD (!), but in this case it is the only way, as there are no APIs as of this date.

        Keyword arguments:
        page_html -- The whole HTML delivered as a string.
        listingid -- The listing id for this given purchase."""

        g_sessionID = self.G_SESSIONID
        g_rgWalletInfo_wallet_currency = 3 #currency is euro
        g_rgListingInfo = re.findall((r'"{0}"\:\{(.*)\}').format(listingid), page_html)
        m_nSubtotal = re.findall(r'"converted_price"\:(.*),', g_rgListingInfo)
        m_nFeeAmount = re.findall(r'"converted_fee"\:(.*),', g_rgListingInfo)
        m_nTotal = int(m_nSubtotal) + int(m_nFeeAmount)

        d = {
            'g_sessionID' : g_sessionID,
            'g_rgWalletInfo_wallet_currency' : g_rgWalletInfo_wallet_currency,
            'm_nSubtotal' : m_nSubtotal,
            'm_nFeeAmount' : m_nFeeAmount,
            'm_nTotal' : m_nTotal,
        }
        return d

    def buy(self, offer_id, buy_info, time_check_start):
        """Performing the transaction. This is sadly the bottleneck in terms of speed,
        as the server is located in Seattle,
        and the post request therefore takes an extremely long (a few hundred milliseconds) to be delivered."""

        buylisting_js = "new Ajax.Request('http://steamcommunity.com/market/buylisting/{0}', {{method: 'post',parameters: {{sessionid: '{1}',currency: '{2}',subtotal: '{3}',fee: '{4}',total: '{5}'}}}});".format(offer_id, buy_info['g_sessionID'], buy_info['g_rgWalletInfo_wallet_currency'], buy_info['m_nSubtotal'], buy_info['m_nFeeAmount'], buy_info['m_nTotal'])
        try:
            print (datetime.datetime.now() - time_check_start).microseconds
            self.browser.execute_script(buylisting_js) # ~100 microseconds + request.. (to Seattle..)
            print 'Item acquired!'
        except:
            print 'Error - Item was not acquired.'
            return

    def send_status_mail(self):
        """Sending a status mail to the default email, every ~3. hour."""

        time_since_start = time.time() - self.start_time

        items_found_data_string = ''
        for i in self.items_found_data:
            items_found_data_string = items_found_data_string + '{0}: {1} euro, {2:.2f}% off (seller: {3})\n'.format(i[0], i[1], i[2], i[3])

        item_data_string = ''
        for i in self.items:
            item_data_string = item_data_string + '{0}: {1:.2f} euro\n'.format(i.name, i.average_price)

        try:
            f = open('mail-template.txt','r')
            mail_data = f.read()
            mail_data = mail_data.format(self.start_date,
            time_since_start/3600,
            (time_since_start/60)%60,
            self.loops,
            self.highest_percent_cheaper_found,
            self.items_found,
            items_found_data_string,
            item_data_string)

            mail = mailself.Mail()
            mail.send('Subject: {0}\n\n{1}'.format('Steam market bot update', mail_data))
            mail.close()
            print 'Update-mail sent!\n-----'
        except:
            print 'Error - update-mail not sent!'

    def init_browser(self):
        """Initializing the browser object, which handels the ajax post request. An unfortunate way of doing it, but sadly the only way, as an 'ajax-method-handler' is not (yet) implemented in Python."""

        browser = Browser('chrome')

        try:
            browser.visit('https://steamcommunity.com/login/home/?goto=market%2F')
        except socket.timeout:
            pass

        return browser

#Non-class functions
def get_page_source(http, item_name):
    """Getting the HTML source for either the newest items or - if specified by item_name - a single type of item.

    Keyword arguments:
    http -- An httplib2.Http() object.
    item_name -- Item name of that given item."""

    cookies = 'steamLogin=COOKIE; steamRememberLogin=COOKIE' # add your own cookies

    if item_name:
        url = MARKET_BASE_URL+'listings/570/{0}'.format(item_name.replace('%', '%25').replace(' ', '%20').replace('(', '%28').replace(')', '%29'))
    else:
        url = MARKET_BASE_URL

    try:
        resp, content = http.request(url, headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.65 Safari/537.31',
 'Cookie': cookies})
        if resp['status'] == '200':
            print resp['content-location']
            return content
    except:
        return

def fetch_item_offers(page_html, item_name):
    """Fetching the offers from the HTML source.
    Parcing HTML is BAD (!!), but in this case it is the only way, as there are no APIs as of this date.

    Keyword arguments:
    page_html -- The whole HTML delivered as a string.
    item_name -- Item name of that given item."""

    ids = re.findall(r"javascript\:BuyMarketListing\('listing', '(\d+)', 570, '2', '(\d+)'\)", page_html)
    item_name = re.findall(r'class="market_listing_item_name".*>(.*)</span>', page_html)
    item_price = re.findall(r'market_listing_price_with_fee">\s+(.*)\s+</span', page_html)
    item_seller = re.findall(r'a href="http://steamcommunity.com/(id|profiles)/(.*)" >', page_html)

    for i in item_price:
        if not '&#8364;' in i:
            sys.exit() #fatal error, if the server rejects the cookie. The price should ALWAYS (!!) be in euro.

    offers = []
    for i in xrange(len(ids)):
        d = {
            'item_name' : item_name[i],
            'id' : ids[i][0],
            'id2' : ids[i][1],
            'price' : float(item_price.replace('&#8364;', '')[i]),
            'seller' : item_seller[i],
        }
        offers.append(d)
    return offers

def average_price(offers):
    """Returns the average price of a set of items.
    The first item is ignored as this is hopefully underpriced.
    The last item is ignored as it is often greatly overpriced.

    IMPORTANT: It is important to only trade items with are represented on the market in great numbers.
    This is due to the fact that with lower competition between sellers, the prices are often non-competitive.

    Keyword arguments:
    offers -- A list of offers from which to find the average price."""

    if len(offers) > 1:
        remove_last_item = (True if (len(offers) > 3) else False)

        cheapest_item = offers[0]['price']
        if remove_last_item:
            sum_ = sum(x['price'] for x in offers[1:-1])
        else:
            sum_ = sum(x['price'] for x in offers[1:])

        return sum_ / (len(offers) - (2 if remove_last_item else 1))

def rand_sleep(min_time=2):
    """Sleeping a random amount of seconds. This should be done after each request to the server, to lower the negative impact on them, due to a high amount of requests. Remember to be a good internet citizen!"""

    sleep_time_in_seconds = random.randint(min_time, min_time+1)
    print '-----\nSleeping for {0}s'.format(sleep_time_in_seconds)
    sleep(sleep_time_in_seconds)
    print '-----'

if __name__ == '__main__':
    bot = Market_bot()
    bot.run()

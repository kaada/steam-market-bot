#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
mail_self.py
Olav Kaada, 2012

Software for simplifing the sending of email through code.
As of this moment, modifying the code with the requested info is needed before use.
"""

import smtplib
from email.mime.text import MIMEText

class Mail:
    server = None

    def __init__(self):
        """Initializing the connection with the gmail server. The mail is sent as a SMTP transmission."""

        self.server = smtplib.SMTP('smtp.gmail.com', 587)

        self.server = smtplib.SMTP()
        self.server.connect("smtp.gmail.com", "submission")
        self.server.starttls()
        self.server.ehlo()
        self.server.login('USERNAME@gmail.com', 'APP_SPECIFIC_PASSWORD')

    def send(self, message):
        """Sending the message to the gmail server for processing.

        Keyword arguments:
        message -- The mail to be sent to server."""

        me = 'USERNANE@gmail.com'
        you = 'USERNAME@gmail.com'
        #message: 'Subject: {0}\n\n{1}'.format(Subject, Text)'
        self.server.sendmail(me, you, message)

    def close(self):
        """Closing the connection with the gmail server."""

        self.server.close()

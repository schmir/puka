import os
import puka
import random
import base


AMQP_URL=os.getenv('AMQP_URL')

class TestBasic(base.TestCase):
    def test_simple_roundtrip(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body=self.msg)
        client.wait(ticket)

        consume_ticket = client.basic_consume(queue=self.name)
        result = client.wait(consume_ticket)
        client.basic_ack(result)
        self.assertEqual(result['body'], self.msg)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_purge(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body=self.msg)
        client.wait(ticket)

        ticket = client.queue_purge(queue=self.name)
        r = client.wait(ticket)
        self.assertEqual(r['message_count'], 1)

        ticket = client.queue_purge(queue=self.name)
        r = client.wait(ticket)
        self.assertEqual(r['message_count'], 0)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_basic_get_ack(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        for i in range(4):
            ticket = client.basic_publish(exchange='', routing_key=self.name,
                                          body=self.msg+str(i))
            client.wait(ticket)

        msgs = []
        for i in range(4):
            ticket = client.basic_get(queue=self.name)
            result = client.wait(ticket)
            self.assertEqual(result['body'], self.msg+str(i))
            self.assertEqual(result['redelivered'], False)
            msgs.append( result )

        ticket = client.basic_get(queue=self.name)
        result = client.wait(ticket)
        self.assertEqual('body' in result, False)

        self.assertEqual(len(client.channels.free_channels), 1)
        self.assertEqual(client.channels.free_channel_numbers[-1], 6)
        for msg in msgs:
            client.basic_ack(msg)
        self.assertEqual(len(client.channels.free_channels), 5)
        self.assertEqual(client.channels.free_channel_numbers[-1], 6)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_basic_publish_bad_exchange(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        for i in range(2):
            ticket = client.basic_publish(exchange='invalid_exchange',
                                          routing_key='xxx', body='')

            self.assertEqual(len(client.channels.free_channels), 0)
            self.assertEqual(client.channels.free_channel_numbers[-1], 2)

            with self.assertRaises(puka.NotFound) as cm:
                client.wait(ticket)

            (r,) = cm.exception # unpack args of exception
            self.assertTrue(r.is_error)
            self.assertEqual(r['reply_code'], 404)

            self.assertEqual(len(client.channels.free_channels), 0)
            self.assertEqual(client.channels.free_channel_numbers[-1], 1)


    def test_basic_return(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      mandatory=True, body='')
        with self.assertRaises(puka.NoRoute):
            client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      mandatory=True, body='')
        client.wait(ticket) # no error

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      mandatory=True, immediate=True, body='')
        with self.assertRaises(puka.NoConsumers):
            client.wait(ticket)


    def test_persistent(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body=self.msg) # persistence=default
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body=self.msg,
                                      headers={'persistent':True})
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body=self.msg,
                                      headers={'persistent':False})
        client.wait(ticket)

        ticket = client.basic_get(queue=self.name, no_ack=True)
        result = client.wait(ticket)
        self.assertTrue(result['headers']['persistent'])
        self.assertEquals(result['headers']['delivery_mode'], 2)

        ticket = client.basic_get(queue=self.name, no_ack=True)
        result = client.wait(ticket)
        self.assertTrue(result['headers']['persistent'])
        self.assertEquals(result['headers']['delivery_mode'], 2)

        ticket = client.basic_get(queue=self.name, no_ack=True)
        result = client.wait(ticket)
        self.assertTrue(not result['headers']['persistent'])
        self.assertTrue('delivery_mode' not in result['headers'])

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_basic_reject(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body='a')
        client.wait(ticket)

        t = client.basic_get(queue=self.name)
        r = client.wait(t)
        self.assertEqual(r['body'], 'a')
        self.assertTrue(not r['redelivered'])
        client.basic_reject(r)

        t = client.basic_get(queue=self.name)
        r = client.wait(t)
        self.assertEqual(r['body'], 'a')
        self.assertTrue(r['redelivered'])
        client.basic_reject(r, False)

        t = client.basic_get(queue=self.name)
        r = client.wait(t)
        self.assertTrue(r['empty'])

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_properties(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        t = client.queue_declare(queue=self.name)
        client.wait(t)

        headers = {
            "content_type": 'a',
            "content_encoding": 'b',
            #"headers": ,
            #"delivery_mode": ,
            "priority": 1,
            "correlation_id": 'd',
            "reply_to": 'e',
            "expiration": 'f',
            "message_id": 'g',
            "timestamp": 1,
            "type_": 'h',
            "user_id": 'i',
            "app_id": 'j',
            "cluster_id": 'k',
            "custom": 'l',
            }

        t = client.basic_publish(exchange='', routing_key=self.name,
                                 body='a', headers=headers.copy())
        client.wait(t)

        t = client.basic_get(queue=self.name, no_ack=True)
        r = client.wait(t)
        self.assertEqual(r['body'], 'a')
        recv_headers = r['headers']
        del recv_headers['delivery_mode']
        del recv_headers['persistent']

        self.assertEqual(headers, recv_headers)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_basic_ack_fail(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body='a')
        client.wait(ticket)

        ticket = client.basic_consume(queue=self.name)
        result = client.wait(ticket)

        with self.assertRaises(puka.PreconditionFailed):
            r2 = result.copy()
            r2['delivery_tag'] = 999
            client.basic_ack(r2)
            client.wait(ticket)

        ticket = client.basic_consume(queue=self.name)
        result = client.wait(ticket)
        client.basic_ack(result)

        with self.assertRaises(AssertionError):
            client.basic_ack(result)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)


    def test_basic_cancel(self):
        client = puka.Client(AMQP_URL)
        ticket = client.connect()
        client.wait(ticket)

        ticket = client.queue_declare(queue=self.name)
        client.wait(ticket)

        for i in range(2):
            ticket = client.basic_publish(exchange='', routing_key=self.name,
                                          body='a')
            client.wait(ticket)

        consume_ticket = client.basic_consume(queue=self.name)
        msg1 = client.wait(consume_ticket)
        self.assertEqual(msg1['body'], 'a')
        client.basic_ack(msg1)

        client.basic_cancel(consume_ticket)
        msg2 = client.wait(consume_ticket)
        result = client.wait(consume_ticket)
        self.assertTrue('consumer_tag' in result)

        ticket = client.basic_publish(exchange='', routing_key=self.name,
                                      body='b')
        client.wait(ticket)

        ticket = client.queue_delete(queue=self.name)
        client.wait(ticket)

#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from flask import Flask, request, redirect
from flask_sockets import Sockets
import gevent
from gevent import queue
import json
import os


app = Flask(__name__)
sockets = Sockets(app)
app.debug = True


class World:
    def __init__(self):
        self.clear()
        self.listeners = list() # We've got listeners now!

    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        '''update the set listeners'''
        #print "UPDATE LISTENERS"
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()


# Code for Client, send_all, send_all_json by Abram Hindle,
# URL: https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py,
# License:  Apache License, Version 2.0
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

clients = list()


def send_all(msg):
    #print "UPDATE CLIENTS"
    for client in clients:
        client.put(msg) # Update each client


def send_all_json(obj):
    send_all(json.dumps(obj)) # Call to update clients


def set_listener( entity, data ):
    ''' do something with the update ! '''
    #print "SET LISTENER"
    send_all_json({entity:data}) # Will eventually update clients


myWorld.add_set_listener(set_listener)


@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect("/static/index.html")


# Code for read_ws based on code by Abram Hindle
# URL: https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
# License:  Apache License, Version 2.0
# Read from socket
def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    try:
        while True:
            msg = ws.receive()
            #print "WS RECV: %s" % msg
            if (msg is not None):
                packet = json.loads(msg)
                #print "PACKET", packet
                #print "ENTITY", packet.keys()[0]
                #print "DATA", packet.values()[0]
                entity = packet.keys()[0] # Get entity
                data = packet[entity]     # Get data
                myWorld.set(entity, data) # Update world (which will eventually update clients)
            else:
                break
    except:
        '''Done'''


# Code for subscribe_socket based on code by Abram Hindle
# URL: https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
# License:  Apache License, Version 2.0
# Write to socket
@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    clients.append(client)
    #print "ADD CLIENT"
    # Want new client to have current state of world when they join,
    # so we have to get them up to speed
    world = myWorld.world()
    for entity in world.keys():
        data = world[entity]
        myWorld.set(entity, data)
    g = gevent.spawn(read_ws, ws, client)
    try:
        while True:
            msg = client.get()
            #print "Got a message!", ws, msg
            ws.send(msg)
    except Exception as e:
        print "WS Error %s" % e
    finally:
        clients.remove(client)
        gevent.kill(g)


def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    #print "UPDATE"
    data = flask_post_json()
    myWorld.set(entity, data)
    data = json.dumps(myWorld.get(entity))
    return data


@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    #print "WORLD"
    data = json.dumps(myWorld.world())
    return data


@app.route("/entity/<entity>")    
def get_entity(entity):
    #print "GET ENTITY"
    '''This is the GET version of the entity interface, return a representation of the entity'''
    data = json.dumps(myWorld.get(entity))
    return data


@app.route("/clear", methods=['POST','GET'])
def clear():
    #print "CLEAR"
    '''Clear the world out!'''
    data = json.dumps(myWorld.clear())
    return data


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    # Re: How to run app based on code by Abram Hindle
    # URL: https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
    # License:  Apache License, Version 2.0
    os.system("bash run.sh")
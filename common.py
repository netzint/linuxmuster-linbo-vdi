#!/usr/bin/env python3

# True => running service on server VM,
# False => remote
global vdiLocalService
vdiLocalService = True
#vdiServiceLocal = False

def dbprint(println):
    debugging = True
    if debugging:
        print (println)

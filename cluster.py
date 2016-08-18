# -*- coding: utf-8 -*-
from datetime import datetime
import argparse
import logging
import json
import sys
import os.path

import config
import db
import utils
import numpy as np

from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import linkage
from scipy.cluster.hierarchy import fcluster

from names import POKEMON_NAMES

def learn_clusters():
    
    if(np.logical_and(os.path.exists('rates.txt'),os.path.exists('locs.txt'))):
       
        rates = np.loadtxt('rates.txt')
        locs = np.loadtxt('locs.txt')
    else:
        
        # load spawnpoints including spawnnumbers
        session = db.Session()
        spawnpoints = db.get_spawnpoints(session)
        session.close()
    
        # extract spawnrates
        rates = np.zeros(shape=(spawnpoints.rowcount,151))
        locs = np.zeros(shape=(spawnpoints.rowcount,2))
        ispawn = 0
        for spawnpoint in spawnpoints:
            for ipoke in xrange(1,152):
                rates[ispawn,ipoke-1] = getattr(spawnpoint, 'poke' + str(ipoke))/spawnpoint.spawnnumber
                locs[ispawn,0] = spawnpoint.lat
                locs[ispawn,1] = spawnpoint.lon
    
            ispawn = ispawn + 1

        np.savetxt('rates.txt',rates)
        np.savetxt('locs.txt',locs)

    # cluster, use correlation as distance measure, the second argument of fcluster is the
    # essential parameter here, this will probably need some tuning to work worldwide with
    # for different data qualities
    link = linkage(np.transpose(rates), 'single', 'correlation')
    clust = fcluster(link,0.6,'distance')

    # count pokemons in each cluster
    clustsize, edges = np.histogram(clust,np.append(np.unique(clust),np.max(clust)+1))
    
    # aggregate spawnrates over clusters
    aggregrates = np.zeros(shape=(len(rates[:,1]),clust.max()))
    for iclust in np.unique(clust):
        aggregrates[:,iclust-1] = np.transpose(np.sum(rates[:,np.where(clust==iclust)],2))
        if(np.sum(aggregrates[:,iclust-1])==0):
            clustsize[iclust-1] = 0

        s = 'found biome: '
        if(clustsize[iclust-1]>3):
            for ipoke in np.where(clust==iclust)[0]:
                s = s + POKEMON_NAMES[ipoke+1] + ' '
            print(s + '(size: ' + str(clustsize[iclust-1]) + ')')

    # macrobiomes = cluster with less than 4? pokemon is enriched with more than 10% across
    # more than 1% of spawnpoints

    b_macrobiome = np.logical_and(np.sum(aggregrates>0.1,axis=0)/len(rates[:,1])>0.01,clustsize<4)

    # assign biomes
    markers = []
    for ispawn in range(len(rates[:,1])):
        nest = []
        biome = []
        macrobiome = []
        nestid = 0;
        for iclust in np.unique(clust):
            # is the cluster enriched?
            if(aggregrates[ispawn,iclust-1]>0.1):
                if(clustsize[iclust-1]>0):
                    if(clustsize[iclust-1]==1):
                        # nest or macrobiome
                        if(b_macrobiome[iclust]):
                            for ipoke in np.where(clust==iclust)[0]:
                                macrobiome.append(POKEMON_NAMES[ipoke+1])
                        else:
                            for ipoke in np.where(clust==iclust)[0]:
                                nest.append(POKEMON_NAMES[ipoke+1])
                                nestid = int(ipoke+1)
                    else:
                        # biome
                        if(clust[54]==iclust): # psyduck for water
                            biome.append('water')
                        elif(clust[16]==iclust): #pidgey for normal
                            biome.append('normal')
                        elif(clust[96]==iclust): #drowzee for psychic
                            biome.append('psychic')
                        elif(clust[13]==iclust): #weedle for bug
                            biome.append('bug')
                        else:
                            s = 'unknown biome:'
                            for ipoke in np.where(clust==iclust)[0]:
                                s = s + POKEMON_NAMES[ipoke+1] + ' '
                            biome.append(s)

        markers.append({
            'id': ispawn,
            'nest': nest,
            'nest_id': nestid,
            'biome': biome,
            'macrobiome': macrobiome,
            'lat': locs[ispawn,0],
            'lon': locs[ispawn,1],
        })

    with open('spawnmarkers.json', 'w') as outfile:
            json.dump(markers, outfile)








if __name__ == '__main__':
    learn_clusters()

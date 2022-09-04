import subprocess
import sys
import json
from typing import List
import csv
from snscrape.base import ScraperException
import snscrape.modules.twitter as st
import multiprocessing
import itertools
import pandas as pd
import os
from tempenv import TemporaryEnvironment




def get_user_tweets(user: str):



    print(user)
    sns_user = st.TwitterUserScraper(user)
    try:
        sns_generator = sns_user.get_items()
    except ScraperException:
        return None
    tweets = itertools.islice(sns_generator , n_tweets)

    tweet_ids = map(lambda x: x.id, tweets)

    raw_mentions = map(lambda x: x.mentionedUsers, tweets)
    mentions = []
    try:
        for i in raw_mentions:
            if i and i[0]:
                mentions.append(i[0].username)
    except ScraperException:
        return None
    try:
        user_result = sns_user._get_entity()

    except KeyError:
        user_info = {"potentially_banned" : True}
    else:
        if user_result:
            user_info = {"id" : user_result.id,
                        "display name" : user_result.displayname,
                        "description" : user_result.description,
                        "verified" : user_result.verified,
                        "potentially_banned" : False,
                        "#followers" : user_result.followersCount,
                        "#posts" : user_result.statusesCount,
                        "#friends" : user_result.friendsCount,
                        "#favourites" : user_result.favouritesCount,
                        "location" : user_result.location
                        }
        else:
            user_info = {"potentially_banned" : True}

    return (list(tweet_ids), mentions, user_info)


def get_replies(tweet: int) -> List[str]:

    return []


# def iteration(user: str, user_dict: Dict[str, Tuple[List[int], List[str]]]) -> Set[str]:
def iteration(args):
    """
    gets tweets ids and mentions from one user
    adds mentions to new_users
    goes through all tweets and adds all mentions from there to new_users
    returns the set of new users

    user: name of the user
    user_dict: central storage of collected data

    Returns: set of all newly found users
    """
    user, user_dict = args[0], args[1]
    dict_update = get_user_tweets(user)

    if not dict_update:
        return None

    new_users = dict_update[1]


    return (new_users, (user, dict_update))


def start_from_user(user: str, max_it: int = 1, n_tweets: int = 100):

    # user_dict = { "user_id" : ( tweet_ids,  mentions)}
    user_dict = {}

    visited_users = set(user)
    
    result = iteration((user, user_dict))
    new_users = set(result[0])
    user_dict[user] = result[1][1]
    users_to_update_with = set()

    i = 0
    pool = multiprocessing.Pool(processes=12)
    while i < max_it:
        i += 1
        print(f"Depth {i}\n lengtht of user dict: {len(user_dict.keys())}")

        # print(type(new_users))
        # if not isinstance(new_users, set):
        #     print(list(new_users))
        #     print(type(list(new_users)[0]))
        #     new_users = set(new_users)
        # print(type(list(new_users)[0]))
        # print(type(visited_users))
        new_users = new_users.difference(visited_users)

        data = [(sub_user, user_dict) for sub_user in new_users if sub_user]

        result = pool.map(iteration, data)

        visited_users.update(new_users)
        
        users_to_update_with = filter(None, map(lambda x: x[0] if x else None, result))
        # print(users_to_update_with)
        dict_updates = filter(None, map(lambda x: x[1] if x else None, result))
        for user_name, content in dict_updates:
            user_dict[user_name] = content
            
        
        
        new_users = set([user for user_list in users_to_update_with for user in user_list if user])
        users_to_update_with = set()

    return user_dict
if __name__ == "__main__":
    # if sys.argv[3] == 'method1':
    #     method1()
    # elif sys.argv[3] == 'method2':
    #     method2()
    # else:
    #     print("Invalid argument")
    

    start_user = sys.argv[1]
    depth = int(sys.argv[2])
    global n_tweets
    n_tweets = int(sys.argv[3])

    edges = []
    user_info = {}
    result_dict = start_from_user(start_user, depth, n_tweets)
    for user, content in result_dict.items():
        for mentioned in content[1]:
            edges.append((user,mentioned))

    col_a = set(list(map(lambda x: x[0], edges)))

    edges_set =  set(edges)
    out_edges = []


    for edge in edges:
        if (edge[1], edge[0]) in edges_set:
            out_edges.append(edge)
            try:
                user_info[edge[0]] = result_dict[edge[0]][2]
            except KeyError:
                continue

    len_node_info = len(user_info.keys())
    unique_nodes = len(set(map(lambda x: x[0], out_edges)))
    print(f"{unique_nodes} unique users in edgelist and {len_node_info} counts of node information")

    user_info_pd = pd.DataFrame.from_dict(user_info, orient = "index")
    user_info_pd.to_csv("user_info.csv")


    with open('edge_list.csv', 'w') as handle:
        writer = csv.writer(handle)
        writer.writerows(out_edges)
    with open('user_info.json', 'w') as handle:
        json.dump(user_info, handle)

    environment = os.environ              
    environment["R_LIBS_USER"] = os.getcwd() + "/R_libraries"
    with TemporaryEnvironment(environment):
        retcode = subprocess.call("R < network_analysis_tool.R --no-save", shell=True)

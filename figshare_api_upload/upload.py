#!/usr/bin/env python
import hashlib
import json
import os
import dotenv
import sys

import requests
from requests.exceptions import HTTPError

import dotenv
import argparse 

# import any local variables from a dot env
env_file = dotenv.find_dotenv()
dotenv.load_dotenv(env_file)

BASE_URL = os.getenv("FIGSHARE_BASE_URL", "https://api.figshare.com/v2/{endpoint}")
TOKEN = os.getenv("FIGSHARE_TOKEN", "")
FILE_PATH = os.getenv("FIGSHARE_FILE_PATH", "")
TITLE = os.getenv("FIGSHARE_TITLE", "")

CHUNK_SIZE = 1048576

parser = argparse.ArgumentParser()
parser.add_argument("FILE, -f", default=FILE_PATH)
parser.add_argument("--TITLE, -t", required=True, default=FILE_PATH)
parser.add_argument('--BASE_URL, -b', default=BASE_URL)
parser.add_argument('--TOKEN, -t', required=True, default=TOKEN)



def raw_issue_request(method, url, data=None, binary=False):
    headers = {'Authorization': 'token ' + TOKEN}
    if data is not None and not binary:
        data = json.dumps(data)
    response = requests.request(method, url, headers=headers, data=data)
    try:
        response.raise_for_status()
        try:
            data = json.loads(response.content)
        except ValueError:
            data = response.content
    except HTTPError as error:
        print('Caught an HTTPError: {}').format(error.message)
        print('Body:\n', response.content)
        raise

    return data


def issue_request(method, endpoint, *args, **kwargs):
    return raw_issue_request(method, BASE_URL.format(endpoint=endpoint), *args, **kwargs)


def list_articles():
    result = issue_request('GET', 'account/articles')
    print('Listing current articles:')
    if result:
        for item in result:
            print(f"{item['url']} - {item['title']}")
    else:
        print('  No articles.')
    return(result)


def create_article(title):
    data = {
        'title': title  # You may add any other information about the article here as you wish.
    }
    result = issue_request('POST', 'account/articles', data=data)
    print('Created article:', result['location'])

    result = raw_issue_request('GET', result['location'])

    return result['id']


def list_files_of_article(article_id):
    result = issue_request('GET', 'account/articles/{}/files'.format(article_id))
    print('Listing files for article {}:').format(article_id)
    if result:
        for item in result:
            print('  {id} - {name}').format(**item)
    else:
        print('  No files.')



def get_file_check_data(file_name):
    with open(file_name, 'rb') as fin:
        md5 = hashlib.md5()
        size = 0
        data = fin.read(CHUNK_SIZE)
        while data:
            size += len(data)
            md5.update(data)
            data = fin.read(CHUNK_SIZE)
        return md5.hexdigest(), size


def initiate_new_upload(article_id, file_name):
    endpoint = 'account/articles/{}/files'
    endpoint = endpoint.format(article_id)

    md5, size = get_file_check_data(file_name)
    data = {'name': os.path.basename(file_name),
            'md5': md5,
            'size': size}

    result = issue_request('POST', endpoint, data=data)
    print('Initiated file upload:', result['location'])

    result = raw_issue_request('GET', result['location'])

    return result


def complete_upload(article_id, file_id):
    issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))


def upload_parts(file_info):
    url = '{upload_url}'.format(**file_info)
    result = raw_issue_request('GET', url)

    print('Uploading parts:')
    with open(FILE_PATH, 'rb') as fin:
        for part in result['parts']:
            upload_part(file_info, fin, part)


def upload_part(file_info, stream, part):
    udata = file_info.copy()
    udata.update(part)
    url = '{upload_url}/{partNo}'.format(**udata)

    stream.seek(part['startOffset'])
    data = stream.read(part['endOffset'] - part['startOffset'] + 1)

    raw_issue_request('PUT', url, data=data, binary=True)
    print('  Uploaded part {partNo} from {startOffset} to {endOffset}').format(**part)


def main(file_path=FILE_PATH, title=TITLE):
    # check to see if title/article already exists
    articles = list_articles()
    for article_index, article in enumerate(articles):
        if article['title'] == TITLE:
            title_exists = True
            break
        else:
            title_exists = False        

    if title_exists:
        article_id = articles[article_index]['id']
        print(f"Title {TITLE} already exists, replacing with file {FILE_PATH}.") 
    else:
        print(f"No record found for {TITLE}, creating new with file {FILE_PATH}")
        article_id = create_article(TITLE)
        list_articles()

    list_files_of_article(article_id)

    # Then we upload the file.
    file_info = initiate_new_upload(article_id, FILE_PATH)
    # Until here we used the figshare API; following lines use the figshare upload service API.
    upload_parts(file_info)
    # We return to the figshare API to complete the file upload process.
    complete_upload(article_id, file_info['id'])
    list_files_of_article(article_id)


if __name__ == '__main__':
    #args = parser.parse_args()
    main()

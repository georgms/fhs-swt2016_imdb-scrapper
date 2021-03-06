import argcomplete
import argparse
import json
import logging
import sys
import urllib2
import time
from functools import wraps
import re
from datetime import date
from bs4 import BeautifulSoup

def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck, e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print msg
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry

# Generates a movie json
def gen_json(movies):
    with open('movies.json', mode='w') as moviesjson:
        json.dump(movies, moviesjson)

# Requests the IMDb data for a given url
def process_page(url):
    try:
        # Retrieve html and setup parser
        @retry(Exception, tries=20, delay=5, backoff=2)
        def urlopen_with_retry():
            return urllib2.urlopen(url)

        soup = BeautifulSoup(urlopen_with_retry(), 'html.parser')

        # Process all table rows
        for tr in soup.find_all('tr', attrs={'class': re.compile(r"^(even|odd)$")}):
            title_container = tr.find('td', attrs={'class': 'title'})

            # Parse single movie information
            try:
                id = title_container.find('a')['href'][8:-1]
            except:
                id = 'n.a.'

            try:
                title = title_container.find('a').contents[0]
            except:
                title = 'n.a.'

            try:
                year = title_container.find('span', attrs={'class': 'year_type'}).string[1:-1]
            except:
                year = 'n.a.'

            try:
                director = title_container.find('span', attrs={'class': 'credit'}).find('a').contents[0]
            except:
                director = 'n.a.'

            try:
                runtime = title_container.find('span', attrs={'class': 'runtime'}).string
            except:
                runtime = 'n.a.'

            try:
                outline = title_container.find('span', attrs={'class': 'outline'}).string
            except:
                outline = 'n.a.'

            try:
                # Build the poster image url based on the cover image url (poster image is higher width and height values)
                image_url = tr.find('td', attrs={'class': 'image'}).find('a').find('img')['src'][
                            :-27] + '._V1_UX182_CR0, 0, 182, 268AL_.jpg'
            except:
                image_url = 'n.a.'

            try:
                certificate = title_container.find('span', attrs={'class': 'certificate'}).find('span')['title']
            except:
                certificate = 'n.a.'

            # Parse actors
            try:
                actors = list()
                actors_temp = title_container.find('span', attrs={'class': 'credit'}).find_all('a')
                for i, a in enumerate(actors_temp):
                    if i != 0:
                        actors.append(actors_temp[i].contents[0])
            except:
                actors = 'n.a.'

            # Parse genres
            try:
                genres = list()
                genres_temp = title_container.find('span', attrs={'class': 'genre'}).find_all('a')
                for i, a in enumerate(genres_temp):
                    genres.append(genres_temp[i].contents[0])
            except:
                genres = 'n.a.'

            # Store the movie data in a dictionary
            movie = {
                "actor": actors,
                "certification": certificate,
                "director": director,
                "genre": genres,
                "id": id,
                "title": title,
                "outline": outline,
                "image_url": image_url,
                "runtime": runtime,
                "year": year
            }

            # Append the movie data dictionary to the movies dictionary
            movies['movies'].append(movie)

            # Store the update movies dictionary in the json file (after each request)
            if args.storing == 'save':
                gen_json(movies)
                logger.info('Movie with id ' + id + ' stored in "movies.json".')
            else:
                logger.info('Movie with id ' + id + ' hold in RAM. It will be stored later in "movies.json"')
    except:
        logger.error('Unexpected error occurred: '.format(sys.exc_info()[0]))
        gen_json(movies)

# Removes the wrapping dictionary of the data in the json file
def clean_json():
    # Load the dictionary from json file
    with open('movies.json') as f:
        movies = json.load(f)

    # Get the value of the wrapping dictionary
    movies_temp = movies['movies']

    # Store the unwrapped dictionaries
    with open('movies.json', mode='w') as moviesjson:
        json.dump(movies_temp, moviesjson)

# Main
if __name__ == '__main__':
    # Reload does the trick!
    reload(sys)

    # Set default encoding
    sys.setdefaultencoding('utf-8')

    # Define commandline arguments
    parser = argparse.ArgumentParser(description='scrape feature movies from IMDB''s "Most Voted Feature Films" list' , usage='python imdb-page-scrapper.py 10000 save')
    parser.add_argument('number', type=int, help='number of movies to request')
    parser.add_argument('storing', choices=['save', 'unsave'],
                        help='[save] store movies data after each request,[unsave] store movies data after all requests were executed')
    parser.add_argument('--start', type=int, help='the ranking number to start with')
    parser.add_argument('--overwrite', default='yes', choices=['yes', 'no'], help='[yes] overwrite json file, [no] append json file')
    args = parser.parse_args()

    if args.number < 0 or args.number % 50 != 0:
        parser.error('number has to be 50 or a multiple of 50 (e.g. 100, 250, 1500)')

    if args.start != None and (args.start < 0 or args.start % 50 != 0):
        parser.error('--start has to be 1, 50 or a multiple of 50 (e.g. 100, 250, 1500)')

    if args.start != None and args.number >= 100000:
        parser.error('--start can only be set if number is smaller than 100000. IMDB does not serve more than 100000 results for any query. In this case we have to split up the list into decades and do not support -start argument.')

    argcomplete.autocomplete(parser)

    # Set up a specific logger with desired output level
    logging.basicConfig(filename='./logs/imdb-page-scrapper.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logging.getLogger().addHandler(logging.StreamHandler())

    # Only show warnings for urllib2 library
    logging.getLogger('urllib2').setLevel(logging.WARNING)

    if args.start != None:
        START_ID = args.start
    else:
        START_ID = 0

    MAX_ITERATIONS = args.number

    DECADES = [1950, 1960, 1970, 1980, 1990, 2000, 2010, date.today().year]

    if args.overwrite == 'yes':
        # Create a clean json file
        logger.info('JSON file "movies.json" created.')
        with open('movies.json', mode='w') as moviesjson:
            json.dump({'movies': []}, moviesjson)

        # Create a dictionary for the movies
        movies = {'movies': []}
    else:
        # Load the dictionary from json file
        with open('movies.json') as f:
            movies_temp = json.load(f)

        # Create a dictionary for the movies
        movies = {'movies': []}

        # Load data from file into created movies dictionary
        for i in range(0, len(movies_temp)):
            movies['movies'].append(movies_temp[i])

    # Process N films of IMDb
    logger.info('Movie retrieval started.')

    if args.number < 100000:
        for i in range(0, MAX_ITERATIONS / 50):
            # Calculate pagination
            if START_ID == 0:
                pagination = (i * 50) + 1
            else:
                pagination = (i * 50) + (START_ID + 1)

            # Define url
            url = 'http://www.imdb.com/search/title?sort=num_votes&start=' + str(pagination) + '&title_type=feature'
            logger.info('Started scrapping of ' + url + '.')

            # Process page of 50 movies
            process_page(url)
            logger.info('Finished scrapping of ' + url + '.')
    else:
        current_number_of_movies = 0

        # Process each decade
        for i in range(0, len(DECADES) - 1):
            # Build url
            url = 'http://www.imdb.com/search/title?sort=num_votes&start=1&title_type=feature&year=' + str(DECADES[i]) + ',' + str(DECADES[i + 1] - 1)

            # Condition for last pair to prevent "index-out-of-range"
            if i == len(DECADES) - 2:
                url = 'http://www.imdb.com/search/title?sort=num_votes&start=1&title_type=feature&year=' + str(DECADES[i]) + ',' + str(DECADES[i + 1])

            # Retrieve html and setup parser
            @retry(Exception, tries=20, delay=5, backoff=2)
            def urlopen_with_retry():
                return urllib2.urlopen(url)

            soup = BeautifulSoup(urlopen_with_retry(), 'html.parser')

            # Get the number of movies of the decade
            number_of_movies_in_decade = int(soup.find('div', attrs={'id': 'left'}).string[9:-9].replace(',', ''))

            # Scrape each page of the current decade
            for j in range(0, number_of_movies_in_decade / 50):
                pagination = (j * 50) + 1

                if j != 0:
                    # Define url
                    url = 'http://www.imdb.com/search/title?sort=num_votes&start=' + str(pagination) + '&title_type=feature&year=' + str(DECADES[i]) + ',' + str(DECADES[i + 1])
                    logger.info('Started scrapping of ' + url + '.')

                    # Process page of 50 movies
                    process_page(url)
                    logger.info('Finished scrapping of ' + url + '.')

                    # Increment counter
                    current_number_of_movies += 50

                    # Stop if desired number of movies was reached (inner loop)
                    if current_number_of_movies == MAX_ITERATIONS:
                        break

                # Stop if desired number of movies was reached (outer loop)
                if current_number_of_movies == MAX_ITERATIONS:
                    break

    # Store the updated movies dictionary in the json file (after all movies were retrieved)
    if args.storing == 'unsave':
        gen_json(movies)
        logger.info('All retrieved movies were stored in "movies.json".')

    # Remove the wrapping dictionary
    clean_json()
    logger.info('"movies.json" cleaned up.')

logger.info('Movie retrieval finished.')
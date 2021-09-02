import base64
import os
import time

from gig import ents
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.firefox.options import Options
from utils import tsv

from gnd_info._utils import log

URL = 'http://apps.moha.gov.lk:8090/officerinfo/'


TIME_WAIT = 0.5


def base64_encode(s):
    return base64.b64encode(s.encode()).decode()


def scrape_index():
    firefox_options = Options()
    firefox_options.headless = True
    driver = webdriver.Firefox(firefox_options=firefox_options)

    driver.get(URL)

    data_list = []

    select_district = driver.find_element_by_name('district')
    for option_district in select_district.find_elements_by_tag_name('option'):
        try:
            district_name = option_district.text
            if 'Select' in district_name:
                continue

            log.info(f'Scraping {district_name}')
            district_value = option_district.get_attribute('value')
            district_code = base64_encode(district_value)

            option_district.click()
            time.sleep(TIME_WAIT)

        except StaleElementReferenceException:
            log.error(f'StaleElementReferenceException for {district_name}')
            continue

        select_ds = driver.find_element_by_name('ds')
        for option_ds in select_ds.find_elements_by_tag_name('option'):
            try:
                ds_name = option_ds.text
                if 'Select' in ds_name:
                    continue
                ds_value = option_ds.get_attribute('value')
                ds_code = base64_encode(ds_value)

                ds_url = os.path.join(
                    'http://apps.moha.gov.lk:8090',
                    'gndata/gn_admin/views',
                    'gn_info_search.php?'
                    + f'ds={ds_code}'
                    + f'&district={district_code}',
                )
                data_list.append(
                    dict(
                        district_name=district_name,
                        district_value=district_value,
                        district_code=district_code,
                        dsd_name=ds_name,
                        dsd_value=ds_value,
                        dsd_code=ds_code,
                        dsd_url=ds_url,
                    )
                )
                log.info(f'\tScraped {ds_name} - {ds_url}')
            except StaleElementReferenceException:
                log.error(f'\t StaleElementReferenceException for {ds_name}')
                continue

    driver.quit()

    data_file = '/tmp/gnd_info.index.tsv'
    tsv.write(data_file, data_list)
    n_data_list = len(data_list)
    log.info(f'Wrote {n_data_list} items to {data_file}')


DSD_NAME_MAP = {
    'kalmunayi north': 'Kalmunai Tamil Division',
    'Koralai Pattu North': 'Koralai Pattu North (Vaharai)',
    'Dehiwala-Mount Lavinia': 'Dehiwala',
    'Hanwella': 'Seethawaka',
    # 'Madampagama': 'Madampagama',
    # 'Waduramba': 'Waduramba',
    'Vadamaradchi East (Maruthnkerny)': 'Vadamaradchi East',
    'Mahawa': 'Maho',
    'Nanaddan': 'Nanattan',
    'Four Gravets': 'Matara Four Gravets',
    'Mundalama': 'Mundel',
    'Kantalai': 'Kanthale',
    'Verugal': 'Verugal (Eachchilampattu)',
}


def expand_data(data):
    district_name = data['district_name']
    _ents = ents.get_entities_by_name_fuzzy(
        district_name,
        filter_entity_type='district',
        limit=1,
    )
    if _ents:
        ent = _ents[0]
        data['district_name'] = ent['name']
        data['district_id'] = ent['id']
    else:
        log.warning(f'Could not find GIG Ent for {district_name}')
        data['district_id'] = None

    dsd_name = data['dsd_name']
    dsd_name = DSD_NAME_MAP.get(dsd_name, dsd_name)
    _ents = ents.get_entities_by_name_fuzzy(
        dsd_name,
        filter_entity_type='dsd',
        filter_parent_id=data['district_id'],
        limit=1,
    )
    if _ents:
        ent = _ents[0]
        data['dsd_name'] = ent['name']
        data['dsd_id'] = ent['id']
    else:
        log.warning(f'Could not find GIG Ent for {district_name}/{dsd_name}')
        # print(f"'{dsd_name}': '{dsd_name}',")
        data['dsd_id'] = None

    return data


def expand_index():
    data_file = '/tmp/gnd_info.index.tsv'
    data_list = tsv.read(data_file)

    expanded_data_list = list(
        map(
            expand_data,
            data_list,
        )
    )
    expanded_data_file = '/tmp/gnd_info.index.expanded.tsv'
    tsv.write(expanded_data_file, expanded_data_list)
    n_data_list = len(expanded_data_list)
    log.info(f'Wrote {n_data_list} items to {expanded_data_file}')


if __name__ == '__main__':
    # scrape_index()
    expand_index()

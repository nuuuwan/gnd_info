import base64
import os
import time

from gig import ents
from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.firefox.options import Options
from utils import tsv
from utils.cache import cache

from gnd_info._constants import CACHE_NAME, CACHE_TIMEOUT
from gnd_info._utils import log
from gnd_info.DSD_NAME_MAP import DSD_NAME_MAP
from gnd_info.GND_NAME_MAP import GND_NAME_MAP

URL = 'http://apps.moha.gov.lk:8090/officerinfo/'


TIME_WAIT = 0.5


def base64_encode(s):
    return base64.b64encode(s.encode()).decode()


def scrape_index():
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)

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

    data_file = '/tmp/gnd_info.index.unexpanded.tsv'
    tsv.write(data_file, data_list)
    n_data_list = len(data_list)
    log.info(f'Wrote {n_data_list} items to {data_file}')


def expand_data(data):
    district_name = data['district_name']
    _ents = ents.get_entities_by_name_fuzzy(
        district_name,
        filter_entity_type='district',
        limit=1,
        min_fuzz_ratio=90,
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
        min_fuzz_ratio=90,
    )
    if _ents:
        ent = _ents[0]
        data['dsd_name'] = ent['name']
        data['dsd_id'] = ent['id']
    else:
        log.warning(f'Could not find GIG Ent for {district_name}/{dsd_name}')
        print(f"'{dsd_name}': '{dsd_name}',")
        data['dsd_id'] = None

    return data


def expand_index():
    data_file = '/tmp/gnd_info.index.unexpanded.tsv'
    data_list = tsv.read(data_file)

    expanded_data_list = list(
        map(
            expand_data,
            data_list,
        )
    )
    expanded_data_file = '/tmp/gnd_info.index.unexpanded.tsv'
    tsv.write(expanded_data_file, expanded_data_list)
    n_data_list = len(expanded_data_list)
    log.info(f'Wrote {n_data_list} items to {expanded_data_file}')


@cache(CACHE_NAME, CACHE_TIMEOUT)
def scrape_dsd_page2(dsd_url):
    cached_result = scrape_dsd_page(dsd_url)
    if len(cached_result) != 100 and len(cached_result) != 0:
        return cached_result
    return scrape_dsd_page_nocache(dsd_url)


@cache(CACHE_NAME, CACHE_TIMEOUT)
def scrape_dsd_page(dsd_url):
    return scrape_dsd_page_nocache(dsd_url)


def scrape_dsd_page_nocache(dsd_url):
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)

    gnd_info_list = []
    try:
        driver.get(dsd_url)
        option_100 = driver.find_element_by_xpath("//option[@value='100']")
        option_100.click()

        while True:
            table = driver.find_element_by_id('showtable')
            for tr in table.find_elements_by_tag_name('tr'):
                td_text_list = list(
                    map(
                        lambda td: td.text,
                        tr.find_elements_by_tag_name('td'),
                    )
                )
                if len(td_text_list) != 8:
                    if len(td_text_list) != 0:
                        td_text_list = str(td_text_list)
                        log.warning(f'Invalid table format: {td_text_list}')
                    continue

                (
                    row_num,
                    district_name,
                    dsd_name,
                    gnd_name,
                    gn_name,
                    phone_home,
                    phone_personal,
                    email,
                ) = td_text_list
                gnd_info_list.append(
                    dict(
                        row_num=row_num,
                        district_name=district_name,
                        dsd_name=dsd_name,
                        gnd_name=gnd_name,
                        gn_name=gn_name,
                        phone_home=phone_home,
                        phone_personal=phone_personal,
                        email=email,
                    )
                )

            li_next = driver.find_element_by_id('showtable_next')
            class_ = li_next.get_attribute('class')
            if 'disabled' in class_:
                break
            else:
                li_next.click()
                time.sleep(TIME_WAIT)
    except WebDriverException:
        log.error(f'Could not scrape: {dsd_url}')

    driver.quit()
    return gnd_info_list


def scrape_all_gnds():
    expanded_data_file = '/tmp/gnd_info.index.unexpanded.tsv'
    expanded_data_list = tsv.read(expanded_data_file)

    gnd_info_list = []
    n_data = len(expanded_data_list)
    for i_data, data in enumerate(expanded_data_list):
        dsd_url = data['dsd_url']
        dsd_name = data['dsd_name']
        district_name = data['district_name'].upper()
        gnd_info_list_for_dsd = scrape_dsd_page2(dsd_url)
        n_gnd = len(gnd_info_list_for_dsd)
        log.info(
            f'{i_data}/{n_data} Scraped {n_gnd} GNDs '
            + f'for {district_name}/{dsd_name}'
        )
        gnd_info_list += gnd_info_list_for_dsd
        # break

    gnd_info_file = '/tmp/gnd_info.unexpanded.tsv'
    tsv.write(gnd_info_file, gnd_info_list)
    n_gnd_info_list = len(gnd_info_list)
    log.info(f'Wrote {n_gnd_info_list} items to {gnd_info_file}')


def expand_gnd_info_item(x):
    i_info_item, info_item = x

    info_item['row_num']
    district_name = info_item['district_name']
    dsd_name = info_item['dsd_name']
    gnd_name = info_item['gnd_name']
    gn_name = info_item['gn_name']
    phone_home = info_item['phone_home']
    phone_personal = info_item['phone_personal']
    email = info_item['email']

    if i_info_item % 100 == 0:
        log.info(
            f'# {i_info_item}) Expanding {district_name}/{dsd_name}/{gnd_name}'
        )

    _ents = ents.get_entities_by_name_fuzzy(
        district_name,
        filter_entity_type='district',
        limit=1,
        min_fuzz_ratio=90,
    )
    if _ents:
        ent = _ents[0]
        district_name = ent['name']
        district_id = ent['id']
    else:
        log.warning(f'Could not find GIG Ent for {district_name}')
        district_id = None

    dsd_name = DSD_NAME_MAP.get(dsd_name, dsd_name)
    _ents = ents.get_entities_by_name_fuzzy(
        dsd_name,
        filter_entity_type='dsd',
        filter_parent_id=district_id,
        limit=1,
        min_fuzz_ratio=90,
    )
    if _ents:
        ent = _ents[0]
        dsd_name = ent['name']
        dsd_id = ent['id']
    else:

        # print(
        #     f"'{dsd_name}': '{dsd_name}',  #"
        #     + f" {district_name} ({district_id})"
        # )
        dsd_id = None

    gnd_name = GND_NAME_MAP.get(gnd_name, gnd_name)
    _ents = ents.get_entities_by_name_fuzzy(
        gnd_name,
        filter_entity_type='gnd',
        filter_parent_id=district_id,
        limit=1,
        min_fuzz_ratio=60,
    )
    if _ents:
        ent = _ents[0]
        # if gnd_name != ent['name']:
        #     print('#', i_info_item, gnd_name, ent['name'])
        gnd_name = ent['name']
        gnd_id = ent['id']
    else:
        # log.warning(
        #     f'Could not find GIG Ent for {district_name}/{dsd_name}/{gnd_name}'
        # )
        print(
            f"'{gnd_name}': '{gnd_name}',  "
            + f"# {i_info_item}) "
            + f" {district_name} ({district_id}) + {dsd_name} ({dsd_id})"
        )
        gnd_id = None

    return dict(
        district_id=district_id,
        district_name=district_name,
        dsd_id=dsd_id,
        dsd_name=dsd_name,
        gnd_id=gnd_id,
        gnd_name=gnd_name,
        gn_name=gn_name,
        phone_home=phone_home,
        phone_personal=phone_personal,
        email=email,
    )


def expand_gnd_info():
    gnd_info_file = '/tmp/gnd_info.unexpanded.tsv'
    gnd_info_list = tsv.read(gnd_info_file)

    expanded_gnd_info_list = list(
        map(
            expand_gnd_info_item,
            enumerate(gnd_info_list),
        )
    )

    expanded_gnd_info_list = sorted(
        expanded_gnd_info_list,
        key=lambda d: str(d['district_id'])
        + str(d['dsd_id'])
        + str(d['gnd_id']),
    )

    expanded_gnd_info_file = '/tmp/gnd_info.tsv'
    tsv.write(expanded_gnd_info_file, expanded_gnd_info_list)
    n_expanded_gnd_info_list = len(expanded_gnd_info_list)
    log.info(
        f'Wrote {n_expanded_gnd_info_list} items to {expanded_gnd_info_file}'
    )


if __name__ == '__main__':
    # scrape_index()
    # expand_index()
    # scrape_all_gnds()
    expand_gnd_info()

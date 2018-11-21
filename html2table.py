from html_table_extractor.extractor import Extractor
import os
import pandas as pd
import numpy as np
import re
from itertools import groupby


column2pattern = {
    '公司': r'.+',
    '类型': r'.+',
    '时间': r'.*([1-3][0-9]{3})',
    '名称': r'.+',
    '内容': r'.+',
    '金额': r'(\d{1,3})(,\d{1,3})*(\.\d{1,})?',
    '占比': r'(100|([0-9]{1,2})|([0-9]{1,2}\,[0-9]{1,3}))(\.\d{1,})?%',
    '金额单位': r'.+'
}


def extract_relation(table: pd.DataFrame, relation='客户'):
    table = table.rename(columns=table.iloc[0]).drop([0])

    if relation not in str(table.columns):
        return None

    typeList = {}
    for _, row in table.iterrows():
        l = ''

        for cell in row:
            cell = str(cell).strip()
            if re.search(column2pattern['时间'], cell):
                l += 'Year#'
            elif re.search(column2pattern['占比'], cell):
                l += 'Percent#'
            elif re.search(column2pattern['金额'], cell) and len(cell) > 1:
                l += 'Money#'
            elif re.match('\d+', cell):
                l += 'Number#'
            elif len(cell) < 4:
                l += 'Short#'
            else:
                l += 'Long#'

        if l not in typeList.keys():
            typeList[l] = [_]
        else:
            typeList[l].append(_)

    pattern = max(typeList.keys(), key=lambda x: len(typeList[x]))
    table = table.drop(set(table.index) - set(typeList[pattern]))

    company = ''
    year = ''
    money = ''
    percentage = ''
    for i in table.columns:
        if isinstance(table[i], pd.DataFrame):
            break
        if relation in i:
            company = i
        elif table[i].str.match(column2pattern['时间']).all():
            year = i
        elif table[i].str.match(column2pattern['金额']).all():
            money = i
        elif table[i].str.match(column2pattern['占比']).all():
            percentage = i

    company = table.pop(company)
    year = table.pop(year)
    money = table.pop(money)
    percentage = table.pop(percentage)
    content = table.pop(table.columns[0])
    unit = '元'

    l = pd.concat([company, year, money, percentage, content, unit], axis=1)
    return l.values().tolist()


if __name__ == '__main__':
    path = './table_html/'
    toFile = False
    analyze = True

    for file in os.listdir(path):

        tables = []

        for i, text in enumerate(open(path + file, encoding='utf8').read().split('<br>')):

            if len(text) < 5:
                continue

            table = pd.DataFrame(Extractor(text).parse()._output, index=None, columns=None)

            pre = None
            toDel = []

            for column in table:
                if pre and table[column].equals(table[pre]):
                    toDel.append(column)
                else:
                    pre = column

            table.drop(table.columns[toDel], axis=1, inplace=True)

            if toFile:
                table = table.append(pd.Series([np.nan]), ignore_index=True)
                tables.append(pd.DataFrame(table.values))

            if analyze:
                extract_relation(table, '客户')
                extract_relation(table, '供应商')

        if toFile:
            data = pd.concat(tables)
            data.to_excel('table_excel/' + file + '.xlsx', index=None, columns=None, header=None)
            data.to_csv('table_csv/' + file + '.tsv', sep='\t', encoding='utf8', index=None, columns=None, header=None)

        if analyze:
            pass

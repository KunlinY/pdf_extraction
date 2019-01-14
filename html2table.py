from html_table_extractor.extractor import Extractor
import os
import pandas as pd
import numpy as np
import re
import traceback
import sys


column2pattern = {
    '公司': r'^[^A-Z]+商',
    '类型': r'.+',
    '时间': r'.*([1-3][0-9]{3})',
    '名称': r'.+',
    '内容': r'.+',
    '金额': r'(\d{1,3})(,\d{1,3})*(\.\d{1,})?',
    '占比': r'(100|([0-9]{1,2})|([0-9]{1,2}\,[0-9]{1,3}))(\.\d{1,})?%',
    '金额单位': r'.+'
}


def extract_relation(name, table, relation, rel_index, years=None, unit='万元'):
    table = table.reset_index()

    company = rel_index

    temp = table[company].tolist()
    flag = False
    for i in temp:
        i = re.sub('(\d|,|\.)+', '', i.strip())
        if len(i) == 0:
            flag = True
            break
    if flag:
        return pd.DataFrame()

    if table[company].str.match(column2pattern['公司']).all():
        company = company - 1

    company = table.pop(company)

    year = '未知'
    money = '未知'
    percentage = '未知'

    for i in table.columns[1:]:
        df = table[i]
        if df.str.match(column2pattern['时间']).all():
            year = i
        elif df.str.match(column2pattern['占比']).all():
            percentage = i
        elif df.str.match(column2pattern['金额']).all():
            money = i

    table['未知'] = '未知'

    year = table.pop(year)
    table['未知'] = '未知'
    money = table.pop(money)
    table['未知'] = '未知'
    percentage = table.pop(percentage)
    content = table.pop(table.columns[-1])

    table['单位'] = unit
    unit = table['单位']
    table['公司'] = name
    name = table['公司']
    table['类型'] = relation
    relation = table.pop('类型')

    if years:
        table['时间'] = years
        year = table['时间']

    l = pd.concat([name, relation, year, company, content, money, percentage, unit], axis=1)
    l.columns = ['公司', '类型', '时间', '名称', '内容', '金额', '占比', '金额单位']
    l = l.replace('{客户}', '销售', regex=True)
    l = l.replace('987.654', '', regex=True)

    return l


def divide_table(name, table: pd.DataFrame, relation='客户'):
    # table = table.rename(columns=table.iloc[0]).drop([0])

    clean = pd.DataFrame(columns=['公司', '类型', '时间', '名称', '内容', '金额', '占比', '金额单位'])
    rel_idx = -1

    if relation not in str(table.loc[[0, 1, 2], :]) or len(table.columns) < 4:
        return None
    else:
        for i in reversed(table.columns):
            for j in range(3):
                if relation in table.loc[j, i] and isinstance(table.loc[j, i], str) and len(table.loc[j, i].strip()) < 10:
                    rel_idx = i
                    break

    if rel_idx < 0:
        return None

    typeList = {}
    previousType = ''
    sameCnt = 1
    subTableIndex = []
    year = None
    for _, row in table.iterrows():
        l = ''

        temp = list(set(row))
        if len(temp) == 1 and temp[0] =='987.654':
            continue

        for cell in row:
            cell = str(cell).strip()
            if re.search(column2pattern['时间'], cell):
                l += 'Year#'
            elif re.search(column2pattern['占比'], cell):
                l += 'Percent#'
            elif re.search(column2pattern['金额'], cell) and (len(cell) > 2 or (len(cell) == 2 and cell != '10')):
                l += 'Money#'
            elif re.match('\d+', cell):
                l += 'Number#'
            elif len(cell) < 3 or (len(cell) < 5 and ('计' in cell or '号' in cell or '度' in cell or '入' in cell)):
                l += 'Short#'
            else:
                l += 'Long#'

        if l not in typeList.keys():
            typeList[l] = [_]
        else:
            typeList[l].append(_)

        if previousType == l:
            sameCnt += 1
            subTableIndex.append(_)
        elif l.replace('Short', 'Long') == previousType:
            continue
        else:
            if sameCnt >= 2:
                df = extract_relation(name, table.loc[subTableIndex, :], relation, rel_idx, year)
                clean = pd.concat([clean, df])
                year = None

            if 'Year' in l:
                year = re.search(column2pattern['时间'], str(row)).groups()[0]
            sameCnt = 1
            previousType = l
            subTableIndex = [_]

    if sameCnt >= 2:
        df = extract_relation(name, table.loc[subTableIndex, :], relation, rel_idx, year)
        clean = pd.concat([clean, df])
    return clean


if __name__ == '__main__':

    company_name = {}
    for line in open('id-filename-name.txt', encoding='utf8'):
        line = line.strip().split('\t')
        company_name[line[0]] = line[2]

    key = set()
    for file in os.listdir('answer/'):
        for line in open('answer/' + file, encoding='utf8'):
            line = line.strip().split('\t')

            if len(line) < 4:
                continue

            key.add(line[0] + '\t' + line[1] + '\t' + line[3])

    path = './chapter_table_new/'
    toFile = False
    analyze = True
    ans = set()

    for file in os.listdir(path):

        tables = []
        clean = pd.DataFrame(columns=['公司', '类型', '时间', '名称', '内容', '金额', '占比', '金额单位'])

        try:
            company = company_name[file[:4]]
        except KeyError as e:
            company = file[5:-8]

        truth = set([x for x in key if company in x])

        for i, text in enumerate(open(path + file, encoding='utf8').read().split('<br>')):

            if len(text) < 5:
                continue

            text = text.replace('销售', '{客户}')

            if '客户' not in text and '供应商' not in text:
                continue

            open('target_html/' + company + '.html', 'a', encoding='utf8').write(text.strip() + '\n<br>\n')

            table = Extractor(text).parse()._output

            if '客户' not in str(table) and '供应商' not in str(table):
                continue

            table = pd.DataFrame(table, index=None, columns=None)

            # delete same column
            pre = None
            toDel = []
            for column in table:
                if pre and table[column].equals(table[pre]):
                    toDel.append(column)
                    continue
                else:
                    pre = column
                if all([not x or len(x.strip()) < 3 for x in table[column][1:]]) or table[column].isnull().all():
                    toDel.append(column)
            table.drop(table.columns[toDel], axis=1, inplace=True)

            pre = None
            toDel = []
            for idx, row in table.iterrows():
                if pre and list(row) == pre or row.isnull().all():
                    toDel.append(idx)
                else:
                    pre = list(row)
            table.drop(toDel, axis=0, inplace=True)

            table = table.reset_index()
            del table['index']
            table.columns = list(range(table.shape[1]))

            if toFile:
                table = table.append(pd.Series([np.nan]), ignore_index=True)
                tables.append(pd.DataFrame(table.values))

            if analyze:
                try:
                    if not any([col.str.match('\d+').any() for _, col in table.iterrows()]):
                        continue
                except:
                    pass
                table = table.fillna('987.654')
                try:
                    clean = pd.concat(
                        [clean, divide_table(company, table, '客户'), divide_table(company, table, '供应商')])
                except Exception as e:
                    # traceback.print_exc(file=sys.stdout)
                    # with pd.option_context('display.max_rows', None, 'display.max_columns', None):
                    #     print(table)
                    # print('==============' + file)
                    try:
                        clean = pd.concat(
                            [clean, divide_table(company, table, '客户'), divide_table(company, table, '供应商')])
                    except:
                        pass

        if toFile:
            data = pd.concat(tables)
            data.to_excel('table_excel/' + file + '.xlsx', index=None, columns=None, header=None)
            data.to_csv('table_csv/' + file + '.tsv', sep='\t', encoding='utf8', index=None, columns=None, header=None)

        if analyze:
            clean = clean.reset_index()
            del clean['index']
            clean.to_excel('clean/' + file + '.xlsx', index=None)

            actual = set()

            for _, row in clean.iterrows():
                ans.add(row['公司'] + '\t' + row['类型'] + '\t' + row['名称'].strip())
                actual.add(row['公司'] + '\t' + row['类型'] + '\t' + row['名称'].strip())

            print(company, len(truth), len(actual), len(truth & actual))

    print(len(key))
    print(len(ans))
    print(len(key & ans))

    out = pd.DataFrame()
    for f in os.listdir('./clean'):
        d = pd.read_excel('clean/' + f)
        out = pd.concat([out, d])
    out.drop_duplicates().to_excel('out.xlsx')

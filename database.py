import json
import sqlite3


class DataBase:
    def __init__(self, uid):
        self.__conn = sqlite3.connect(f'./data/sqlite/{uid}.db', check_same_thread=False)
        self.__c = self.__conn.cursor()
        self.__c.execute('CREATE TABLE IF NOT EXISTS DATA(SEQNO INT PRIMARY KEY,MKEY INT,MSG TEXT);')

    def insert(self, seqno, key, data):
        msg = json.dumps(data, indent=4, ensure_ascii=False)
        self.__c.execute('INSERT INTO DATA (SEQNO,MKEY,MSG) VALUES (?,?,?);', (seqno, key, msg))

    def query(self, cmd='*', seqno=None, key=None):
        sql = f'SELECT {cmd} FROM DATA WHERE '
        if seqno:
            sql += f'SEQNO = {seqno}'
        if key:
            if seqno:
                sql += ' AND '
            sql += f'MKEY = {key}'
        return self.__c.execute(sql).fetchone()

    def save(self):
        self.__conn.commit()
import json
import sqlite3


class DataBase:
    def __init__(self):
        self.__conn = sqlite3.connect(f'./data/sqlite/Messages.db', check_same_thread=False)
        self.__c = self.__conn.cursor()
        self.__c.execute('CREATE TABLE IF NOT EXISTS DATA(SEQNO INT PRIMARY KEY,MKEY INT,TALKER INT,MSG TEXT);')

    def insert(self, seqno, key, talker, data):
        msg = json.dumps(data, indent=4, ensure_ascii=False)
        self.__c.execute('INSERT INTO DATA (SEQNO,MKEY,TALKER,MSG) VALUES (?,?,?,?);', (seqno, key, talker, msg))

    def query(self, cmd='*', seqno=None, key=None, talker=None):
        sql = f'SELECT {cmd} FROM DATA WHERE '
        params = []
        if seqno:
            params.append(f'SEQNO = {seqno}')
        if key:
            params.append(f'MKEY = {key}')
        if talker:
            params.append(f'TALKER = {talker}')
        sql += ' AND '.join(params)
        # print(sql)
        return self.__c.execute(sql).fetchone()

    def save(self):
        self.__conn.commit()

    def close(self):
        self.__conn.close()


if __name__ == '__main__':
    db = DataBase()
    msg = db.query(seqno=2, key=1, talker='434334701')
    print(msg)
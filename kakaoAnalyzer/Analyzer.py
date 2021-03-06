from re import search, compile
from datetime import datetime
from tqdm import tqdm
from .msgstruct import *

def open_file(f_name, encoding=None):
    ''' 
    Open KakaoTalk File. 
    'f_name' is file path to open. encoding is encoding type to open.
    It will return file descriptor and the number of lines.
    '''
    linenum = 0

    if not encoding:
        try:
            f = open(f_name, 'r', encoding='utf8')
            while f.readline(): linenum+=1
            f.close()
            f = open(f_name, 'r', encoding='utf8')

            return f, linenum

        except:
            f = open(f_name, 'r')
            while f.readline(): linenum+=1
            f.close()
            f = open(f_name, 'r')

            return f, linenum

    f = open(f_name, 'r', encoding=encoding)
    while f.readline(): linenum+=1
    f.close()
    f = open(f_name, 'r')

    return f, linenum

def select_mode(f_name, encoding):
    fd, _ = open_file(f_name, encoding)
    lines = fd.read(4096)
    fd.close()

    android_exp = '\d{4}년 \d{1,2}월 \d{1,2}일 (?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{2}), (?P<name>.+?) : (?P<con>.+)'
    windows_exp = '\[(?P<name>.+?)\] \[(?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{2})\] (?P<con>.+)'
    ios_exp = '(?P<year>\d{4}). (?P<month>\d{1,2}). (?P<day>\d{1,2}). (?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{1,2}), (?P<name>.+?) : (?P<con>.+?)\r?\n?'
    mac_exp = '(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2}) (?P<hour>\d{1,2}):(?P<min>\d{1,2}):(?P<sec>\d{1,2}),(?P<name>.+),(?P<con>.+)\r?\n?'
    imp_exp = '(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2}) (?P<hour>\d{1,2}):(?P<min>\d{1,2}),(?P<name>.+),(?P<con>.+)\r?\n?'
    exps = (None, android_exp, windows_exp, ios_exp, mac_exp, imp_exp)

    for mode in range(1,6):
        if search(exps[mode], lines):
            return mode

    raise Exception('Cannot find file mode!')

def import_from_csv(f_name, encoding=None, line_analyze=None, preprocessor=None, msg_filter=None, merge=False, date_exp='%Y-%m-%d %H:%M'):
    '''
    This function works like Analyze function, but for csv files.
    f_name: file path to open.
    encoding: file open encoding.
    line_analyze: Function to analyze sentence to words.
    preprocessor: preprocessor function for messages.
    msg_filter: function to filter some messages.
    merge: concurrent messages merge as one message. True / False parameter.
    date_exp: datetime expression in the file like '%Y-%m-%d %H:%M'.
    '''
    from csv import reader

    # File Open
    data_in, linenum  = open_file(f_name, encoding)
    rdr = reader(data_in)
    next(rdr)

    # Set Chatname
    chatname = f_name[:f_name.rfind('.')]

    # Check Text lines
    pbar = tqdm(total=linenum-1)
    chatroom = Chatroom(chatname, line_analyze)
    date_prev = datetime(1,1,1)
    queue = []

    for date, name, content in rdr:
        pbar.update(content.count('\n') + 1)

        # Filtering
        if msg_filter and msg_filter(content):
            continue

        date = datetime.strptime(date, date_exp)

        # Merge Message content to last
        if merge and queue and queue[-1][1]==name and (date-date_prev).seconds <= 60:
            date_prev = date
            queue[-1][2] += '\n' + content
            continue
        
        if queue:
            
            # Preprocess
            if preprocessor:
                queue[0][2] = preprocessor(queue[0][2])
            chatroom.append(*queue[0])
            del queue[0]

        date_prev = date
        queue.append((date, name, content))

    pbar.close()
    return chatroom


def Analyze(f_name, line_analyze=None, encoding=None, preprocessor=None, line_filter=None, msg_filter=None, merge=False):
    '''
    Analyze kakaoTalk text. input parameter is file path.
    'line_analyze' parameter is for spliting words. basic is space spliter.
    you can use kkma analzyer, 'kkma' parameter or you can use your own function.
    encoding is file open encoding option.
    If you want to preprocess message content, you can use preprocessor which should be your own function.
    If you want to filter some messages like deleted message, you can use 'line_filter' parameter.
    'line_filter' should be a function that returns true when the message should be filtered.
    'msg_filter' is similar to 'line_filter', but 'msg_filter' filter only for message content not for a whole line.
    If you want to merge contemporary timed messages, you can pass 'merge=True', 
    Then the messages will be merged like one message.

    It returns Chatroom instance.
    '''

    # Variables, queue is for multiline message.
    loop = 0
    date = None
    date_prev = datetime(1, 1, 1)
    name = ''
    name_prev = ''
    chatname = None
    line = True
    queue = []

    # Select Mode
    mode = select_mode(f_name, encoding)

    # File Open
    data_in, line_num = open_file(f_name, encoding)

    # Find Chatroom Name
    line = data_in.readline().replace('\ufeff', '')
    chatname = search('(.+?) 님과 카카오톡 대화|(.+?) \d+ 카카오톡 대화', line)

    # Set Chatname
    if chatname:
        chatname = chatname.group(1,2)
        chatname = chatname[0] if chatname[0] else chatname[1]
    else:
        chatname = f_name.split('.')[0] + '_Analyzed'

    # Android
    if mode == 1:
        datetime_exp = compile('(?P<year>\d{4})년 (?P<month>\d{1,2})월 (?P<day>\d{1,2})일 .. \d{1,2}:\d{2}\r?\n?$')
        message_exp = compile('\d{4}년 \d{1,2}월 \d{1,2}일 (?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{2}), (?P<name>.+?) : (?P<con>.+)')
        etc_exp = compile('\d{4}년 \d{1,2}월 \d{1,2}일 .. \d{1,2}:\d{1,2}, .+')

    # Windows PC
    elif mode == 2:
        datetime_exp = compile('-+ (?P<year>\d{4})년 (?P<month>\d{1,2})월 (?P<day>\d{1,2})일 .요일 -+\r?\n?')
        message_exp = compile('\[(?P<name>.+?)\] \[(?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{2})\] (?P<con>.+)')
        etc_exp = compile('.+님이 나갔습니다.\r?\n?|.+님이 .+님을 초대하였습니다.\r?\n?|.+님이 들어왔습니다.\r?\n?')

    # ipad
    elif mode == 3:
        chatname = line
        datetime_exp = compile('(?P<year>\d{4})년 (?P<month>\d{1,2})월 (?P<day>\d{1,2})일 .요일\r?\n?')
        message_exp = compile('(?P<year>\d{4}). (?P<month>\d{1,2}). (?P<day>\d{1,2}). (?P<afm>..) (?P<hour>\d{1,2}):(?P<min>\d{1,2}), (?P<name>.+?) : (?P<con>.+?)\r?\n?$')
        etc_exp = compile('\d{4}. \d{1,2}. \d{1,2}. .. \d{1,2}:\d{1,2}: .+')

    # Mac 
    elif mode == 4:
        return import_from_csv(f_name, encoding=encoding, preprocessor=preprocessor, date_exp='%Y-%m-%d %H:%M:%S')

    # Imported
    elif mode == 5:
        return import_from_csv(f_name, encoding=encoding, preprocessor=preprocessor)

    chatroom = Chatroom(chatname, line_analyze)

    # Check Text lines
    pbar = tqdm(total=line_num)

    while line:
        line = data_in.readline()

        # Check line with regular expression
        m_date = datetime_exp.match(line)
        m_message = message_exp.match(line)

        # Only unfiltered Message
        if not (line_filter and line_filter(line)):

            # The case this line is new date.
            if m_date:
                # Excute
                if len(queue) and not merge:
                    if preprocessor:
                        queue[0][2] = preprocessor(queue[0][2])
                    chatroom.append(*queue[0])
                    del queue[0]
                # Update date
                date = datetime(int(m_date.group('year')), int(m_date.group('month')), int(m_date.group('day')))

            # The case this line is new message.
            elif m_message:
                name_prev = name
                name = m_message.group('name')
                afm = m_message.group('afm')
                hour = int(m_message.group('hour'))
                minute = int(m_message.group('min'))
                content = m_message.group('con')

                hour = hour if hour != 12 else 0
                if afm == '오후':
                    hour += 12
                if not (msg_filter and msg_filter(content)):
                    date_prev = date
                    date = date.replace(hour=hour, minute=minute)

                    if merge and name == name_prev and (date-date_prev).seconds <= 60:
                        queue[-1][2] += '\n' + content

                    else:
                        # Excute
                        if len(queue):
                            if preprocessor:
                                queue[0][2] = preprocessor(queue[0][2])
                            chatroom.append(*queue[0])
                            del queue[0]

                        # Enqueue
                        queue.append([date, name, content])

            # The case this line is addition string of last message.
            elif len(queue) and not etc_exp.match(line):
                queue[-1][2] += '\n' + line

        interval = content.count('\n') + 1 if m_message else 1
        pbar.update(interval)
    
    pbar.close()
    
    # Last Dequeuing
    if len(queue):
        if preprocessor:
            queue[0][2] = preprocessor(queue[0][2])
        chatroom.append(*queue[0])

    data_in.close()
    return chatroom

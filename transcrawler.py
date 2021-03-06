import getpass, smtplib, sys, time, traceback
import logging as log
from splinter import Browser
from email.mime.text import MIMEText
# 1. pyhton transcrawler.py
# 2. Ctrl+Z
# 3. bg
# 4. jobs (to get ID)
# 5. disown %(ID)

SMTP_SERVER = 'smtp1.sympatico.ca'

XPATH_PREFIX = '/html/body/div[3]/table[2]'
MINERVA_HOME = 'https://horizon.mcgill.ca/pban1/twbkwbis.P_WWWLogin'
MINERVA_TRANSCRIPT = 'https://horizon.mcgill.ca/pban1/bzsktran.P_Display_Form?user_type=S&tran_type=V'
MINERVA_LOGOUT = 'https://horizon.mcgill.ca/pban1/twbkwbis.P_Logout'

# delay is in seconds
DELAY = 30 * 60

log.basicConfig(filename='transcrawler.log', level=log.INFO,
                format='%(asctime)s - %(levelname)s : %(message)s',
                datefmt='%m/%d/%Y %I:%M:%S %p')

b = Browser('phantomjs')
grades = None


def authenticate():
    if sys.version_info > (3,):
        user = input('Username: ')
    else:
        user = raw_input('Username: ')
    password = getpass.getpass()
    return [user, password]


credentials = authenticate()


def send_mail(receiver, content,
              sender='khalabi@jarvis.inventico.com', sender_name='Transcrawler Service',
              subject='Transcript Update'):

    msg = MIMEText(content, 'plain')
    msg['Subject'] = subject
    msg['From'] = '%s <%s>' % (sender_name, sender)

    try:
        smtp_obj = smtplib.SMTP(SMTP_SERVER)
        smtp_obj.sendmail(sender, receiver, msg.as_string())
        log.info("Successfully sent email")
    except OSError:
        log.error("Error: unable to send email")


def build_grades():
    g = []
    rows = b.find_by_xpath(XPATH_PREFIX).find_by_tag('tr')

    for i in range(len(rows)):
        cells = rows[i].find_by_tag('td')
        # grade rows contain exactly 11 cells
        if len(cells) != 11:
            continue
        # skip rows that already have averages
        avg = cells[10].value.strip()
        if avg != '':
            continue

        course_code = cells[1].value
        # Fix for multi-term courses
        if len(course_code) > 10:
            course_code = course_code[:10]

        # course code          grade            avg
        g.append([course_code, cells[6].value, cells[10].value])
        log.info('Added: %s' % course_code)
    # Don't care about AAAA 100
    g.remove([u'AAAA 100', u'CO', u' '])
    log.info('Removed AAAA 100')

    # Send out a confirmation email
    email = "Updates to the following courses are being monitored:\n\n"

    for course in g:
        email += course[0] + ": "
        if course[1] != ' ':
            email += "Class average\n"
        else:
            email += "Grade and class average\n"

    email += "\nAny changes will be sent out within " \
             + str(DELAY/60) + " minutes.\nThank you for using the Transcrawler service."

    send_mail(credentials[0], email, subject="Confirmation")
    return g


def compare_grades(g):
    update = ''
    i = 0
    while i < len(g):
        grade = g[i]
        course = grade[0]
        old_grade = grade[1]
        old_avg = grade[2] #TODO: can be removed?

        c = b.find_by_xpath('//td[contains(.,\"' + course + '\")]')
        course_row = c.find_by_xpath('.//ancestor::tr')
        new_grade = course_row.find_by_xpath('./td[7]').value
        new_avg = course_row.find_by_xpath('./td[11]').value

        if old_grade != new_grade:
            grade_message = '%s grade has been updated to %s \n' % (course, new_grade)
            log.info(grade_message)
            update += grade_message
            grade[1] = new_grade
            i += 1
        elif old_avg != new_avg:
            avg_message = '%s class avg has been updated to %s \n' % (course, new_avg)
            log.info(avg_message)
            update += avg_message
            g.remove(grade)
        else:
            i += 1
    if len(update) > 0:
        email = 'The following transcript changes have been detected: \n\n' + update + '\n' \
                + 'Log into minerva to confirm these updates'
        send_mail(credentials[0], email)
        log.info('New List:\n%s' % str(grades))


try:
    b.visit(MINERVA_HOME)
    b.find_by_id('mcg_un').fill(credentials[0])
    b.find_by_id('mcg_pw').fill(credentials[1])
    b.find_by_id('mcg_un_submit').click()
    b.visit(MINERVA_TRANSCRIPT)

    grades = build_grades()

    b.visit(MINERVA_LOGOUT)

    while True:
        time.sleep(DELAY)
        b.visit(MINERVA_HOME)
        if b.is_element_not_present_by_id('mcg_un'):
            log.warning('Minerva home missing login, trying again in %d seconds' % DELAY)
            continue
        b.find_by_id('mcg_un').fill(credentials[0])
        b.find_by_id('mcg_pw').fill(credentials[1])
        b.find_by_id('mcg_un_submit').click()
        b.visit(MINERVA_TRANSCRIPT)
        compare_grades(grades)
        log.info('Update complete')
        b.visit(MINERVA_LOGOUT)

except Exception:
    ex_type, ex, tb = sys.exc_info()
    traces = traceback.format_list(traceback.extract_tb(tb))
    message = ''
    for t in traces:
        message += t
    message += '\n' + str(ex)
    log.error(message)
    send_mail(credentials[0], message)

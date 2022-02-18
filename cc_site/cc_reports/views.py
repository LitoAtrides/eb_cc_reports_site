import csv
from datetime import datetime
import psycopg2
from django.shortcuts import render
from django.core.paginator import Paginator
from connect_db import prod_password as password, prod_host as host, user, database, port


def average_call_rep(request):
    csv_data = []
    with open('cc_data.csv', 'rU') as csv_file:
        reader = csv.reader(csv_file, dialect='excel')
        for row in reader:
            csv_data.append(row)
    paginator = Paginator(csv_data, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'cc_reports/calls_rep.html',
                  {'title': 'Звонки по дням', 'reader': page_obj.object_list, 'page_obj': page_obj})


def get_data_drop_call(call_id):
    sql_request = (f"""
            SELECT callcent_ag_dropped_calls.ag_num,
                callcent_ag_dropped_calls.time_start AT TIME ZONE 'UTC',
                callcent_ag_dropped_calls.time_end AT TIME ZONE 'UTC',
                DATE_TRUNC('second', callcent_ag_dropped_calls.ts_polling + interval '500 millisecond'),
                callcent_ag_dropped_calls.reason_noanswerdesc, 
                callcent_ag_dropped_calls.q_call_history_id,
                callcent_queuecalls.from_userpart 
            FROM callcent_ag_dropped_calls 
            LEFT JOIN callcent_queuecalls ON callcent_queuecalls.call_history_id = q_call_history_id 
            WHERE q_call_history_id = '{call_id}' 
            ORDER BY idcallcent_ag_dropped_calls ASC
    """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        drop_calls_rep = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()

    return drop_calls_rep


def drop_call(request):
    call_id = request.GET.get('object')
    drop_call_data = get_data_drop_call(call_id)
    return render(request, 'cc_reports/calls_drop.html',
                  {'title': 'Детализация потеряного звонка', 'reader': drop_call_data})


def get_data_all_drop_call():
    sql_request = (f"""
            SELECT 
                callcent_ag_dropped_calls.ag_num,
                callcent_ag_dropped_calls.time_start AT TIME ZONE 'UTC',
                callcent_ag_dropped_calls.time_end AT TIME ZONE 'UTC',
                DATE_TRUNC('second', callcent_ag_dropped_calls.ts_polling + interval '500 millisecond'), 
                callcent_ag_dropped_calls.reason_noanswerdesc,
                callcent_ag_dropped_calls.q_call_history_id 
            FROM callcent_ag_dropped_calls 
            WHERE reason_noanswerdesc = 'Poll expired' OR reason_noanswerdesc = 'User requested'
            AND time_start AT TIME ZONE 'UTC' > '2021-08-01' 
            ORDER BY idcallcent_ag_dropped_calls DESC
    """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        drop_calls_rep = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()

    return drop_calls_rep


def all_drop_call(request):
    dropped_calls = get_data_all_drop_call()
    paginator = Paginator(dropped_calls, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'cc_reports/all_calls_drop.html',
                  {'title': 'Все потерянные звонки', 'reader': page_obj.object_list, 'page_obj': page_obj})


def get_data_calls_by_operator():
    sql_request = (f"""
            WITH
            Canceled_calls AS (
                SELECT count (*) AS Call_count, ag_num
                FROM callcent_ag_dropped_calls
                WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                GROUP BY ag_num
                ORDER BY ag_num
            ),
            Call_in AS (
                SELECT to_dn AS Operator_ID_in, count (*) AS Calls_by_Operator_in
                FROM callcent_queuecalls
                WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' AND to_dn !=
                '1000' AND to_dn != '1001' AND to_dn != '9999'
                GROUP BY to_dn
                ORDER BY to_dn ASC
            ),
            Call_out AS (
                SELECT count (*) AS Calls_by_Operator_out, si.dn AS Operator_ID_out
                FROM ((((((cl_segments s
                JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                JOIN cl_party_info si ON ((si.id = sp.info_id)))
                JOIN cl_party_info di ON ((di.id = dp.info_id)))
                LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01'
                AND s.action_id = 1 AND si.dn_type = 0 AND di.dn_type = 13 AND seq_order = 1
                AND si.dn != '1000' AND si.dn != '1001'
                GROUP BY si.dn
                ORDER BY si.dn ASC              
            )
            SELECT CAST(Call_in.Operator_ID_in AS int4), Call_in.Calls_by_Operator_in, 
            Call_out.Calls_by_Operator_out, Canceled_calls.Call_count
            FROM Call_in
            INNER JOIN Call_out ON Call_in.Operator_ID_in = Call_out.Operator_ID_out
            INNER JOIN Canceled_calls ON Call_in.Operator_ID_in = Canceled_calls.ag_num
            """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        in_calls = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()

    return in_calls


def get_data_call_by_week_day():
    date_format = "%m/%d/%Y"
    a = datetime.now()
    b = datetime.strptime('1/08/2021', date_format)
    delta = a - b
    week_count = round(delta.days / 7)

    sql_request = f"""
                WITH 
                Canceled_calls AS (
                    SELECT count (*) / {week_count} AS Call_count, to_char(time_start, 'ID') AS Day_of_the_week
                    FROM callcent_ag_dropped_calls 
                    WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                    AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                    AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                    GROUP BY to_char(time_start, 'ID')
                    ),
                Call_in_count AS (
                    SELECT count (*) / {week_count} AS Calls_count_in, to_char(time_start, 'ID') AS Day_of_the_week
                    FROM callcent_queuecalls 
                    WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' 
                    AND to_dn != '1000' AND to_dn != '1001' AND to_dn != '9999'
                    GROUP BY to_char(time_start, 'ID')
                   ),
                Call_out_count AS (SELECT count (*) / {week_count} AS Calls_count_out, 
                to_char(s.start_time, 'ID') AS Day_of_the_week
                    FROM ((((((cl_segments s
                    JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                    JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                    JOIN cl_party_info si ON ((si.id = sp.info_id)))
                    JOIN cl_party_info di ON ((di.id = dp.info_id)))
                    LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                    LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                    WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01' 
                    AND s.action_id = 1 AND si.dn_type = 0 AND seq_order = 1 
                    AND si.dn != '1000' AND si.dn != '1001' AND di.dn_type = 13
                    GROUP BY to_char(s.start_time, 'ID'))
                SELECT Call_out_count.Day_of_the_week, Call_in_count.Calls_count_in, 
                Call_out_count.Calls_count_out, Canceled_calls.Call_count
                FROM Call_in_count
                INNER JOIN Call_out_count ON Call_in_count.Day_of_the_week = Call_out_count.Day_of_the_week
                INNER JOIN Canceled_calls ON  Call_in_count.Day_of_the_week = Canceled_calls.Day_of_the_week
                ORDER BY Call_in_count.Day_of_the_week ASC
    """

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        calls_count = cursor_call_count.fetchall()

        monday = calls_count[0]
        monday = list(monday)
        monday[0] = "Понедельник"
        monday = tuple(monday)
        calls_count[0] = monday

        tuesday = calls_count[1]
        tuesday = list(tuesday)
        tuesday[0] = "Вторник"
        tuesday = tuple(tuesday)
        calls_count[1] = tuesday

        wednesday = calls_count[2]
        wednesday = list(wednesday)
        wednesday[0] = "Среда"
        wednesday = tuple(wednesday)
        calls_count[2] = wednesday

        tuesday = calls_count[3]
        tuesday = list(tuesday)
        tuesday[0] = "Четверг"
        tuesday = tuple(tuesday)
        calls_count[3] = tuesday

        friday = calls_count[4]
        friday = list(friday)
        friday[0] = "Пятница"
        friday = tuple(friday)
        calls_count[4] = friday

        saturday = calls_count[5]
        saturday = list(saturday)
        saturday[0] = "Суббота"
        saturday = tuple(saturday)
        calls_count[5] = saturday

        sunday = calls_count[6]
        sunday = list(sunday)
        sunday[0] = "Воскресенье"
        sunday = tuple(sunday)
        calls_count[6] = sunday

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()

    return calls_count


def index(request):
    data_calls_by_operator = get_data_calls_by_operator()
    data_call_by_week_day = get_data_call_by_week_day
    call_by_operator = render(request, 'cc_reports/index.html', {'title': 'Звонки по операторам',
                                                                 'data_calls_by_operator': data_calls_by_operator,
                                                                 'data_call_by_week_day': data_call_by_week_day})
    return call_by_operator


def get_operator_id():
    sql_request = (f"""
            WITH
            Canceled_calls AS (
                SELECT count (*) AS Call_count, ag_num
                FROM callcent_ag_dropped_calls
                WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                GROUP BY ag_num
                ORDER BY ag_num
            ),
            Call_in AS (
                SELECT to_dn AS Operator_ID_in, count (*) AS Calls_by_Operator_in
                FROM callcent_queuecalls
                WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' AND to_dn !=
                '1000' AND to_dn != '1001' AND to_dn != '9999'
                GROUP BY to_dn
                ORDER BY to_dn ASC
            ),
            Call_out AS (
                SELECT count (*) AS Calls_by_Operator_out, si.dn AS Operator_ID_out
                FROM ((((((cl_segments s
                JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                JOIN cl_party_info si ON ((si.id = sp.info_id)))
                JOIN cl_party_info di ON ((di.id = dp.info_id)))
                LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01'
                AND s.action_id = 1 AND si.dn_type = 0 AND di.dn_type = 13 AND seq_order = 1
                AND si.dn != '1000' AND si.dn != '1001'
                GROUP BY si.dn
                ORDER BY si.dn ASC              
            )
            SELECT CAST(Call_in.Operator_ID_in AS int4)
            FROM Call_in
            INNER JOIN Call_out ON Call_in.Operator_ID_in = Call_out.Operator_ID_out
            INNER JOIN Canceled_calls ON Call_in.Operator_ID_in = Canceled_calls.ag_num
            """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        operator_id = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()
    list_to_str = ' '.join(map(str, operator_id))
    list_to_str = list_to_str.replace("(", "")
    list_to_str = list_to_str.replace(")", "")
    list_to_str = list_to_str.rstrip(list_to_str[-1])

    return list_to_str


def get_operator_in_calls():
    sql_request = (f"""
            WITH
            Canceled_calls AS (
                SELECT count (*) AS Call_count, ag_num
                FROM callcent_ag_dropped_calls
                WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                GROUP BY ag_num
                ORDER BY ag_num
            ),
            Call_in AS (
                SELECT to_dn AS Operator_ID_in, count (*) AS Calls_by_Operator_in
                FROM callcent_queuecalls
                WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' AND to_dn !=
                '1000' AND to_dn != '1001' AND to_dn != '9999'
                GROUP BY to_dn
                ORDER BY to_dn ASC
            ),
            Call_out AS (
                SELECT count (*) AS Calls_by_Operator_out, si.dn AS Operator_ID_out
                FROM ((((((cl_segments s
                JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                JOIN cl_party_info si ON ((si.id = sp.info_id)))
                JOIN cl_party_info di ON ((di.id = dp.info_id)))
                LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01'
                AND s.action_id = 1 AND si.dn_type = 0 AND di.dn_type = 13 AND seq_order = 1
                AND si.dn != '1000' AND si.dn != '1001'
                GROUP BY si.dn
                ORDER BY si.dn ASC              
            )
            SELECT Call_in.Calls_by_Operator_in
            FROM Call_in
            INNER JOIN Call_out ON Call_in.Operator_ID_in = Call_out.Operator_ID_out
            INNER JOIN Canceled_calls ON Call_in.Operator_ID_in = Canceled_calls.ag_num
            """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        operator_id = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()
    list_to_str = ' '.join(map(str, operator_id))
    list_to_str = list_to_str.replace("(", "")
    list_to_str = list_to_str.replace(")", "")
    list_to_str = list_to_str.rstrip(list_to_str[-1])

    return list_to_str


def get_operator_out_calls():
    sql_request = (f"""
            WITH
            Canceled_calls AS (
                SELECT count (*) AS Call_count, ag_num
                FROM callcent_ag_dropped_calls
                WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                GROUP BY ag_num
                ORDER BY ag_num
            ),
            Call_in AS (
                SELECT to_dn AS Operator_ID_in, count (*) AS Calls_by_Operator_in
                FROM callcent_queuecalls
                WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' AND to_dn !=
                '1000' AND to_dn != '1001' AND to_dn != '9999'
                GROUP BY to_dn
                ORDER BY to_dn ASC
            ),
            Call_out AS (
                SELECT count (*) AS Calls_by_Operator_out, si.dn AS Operator_ID_out
                FROM ((((((cl_segments s
                JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                JOIN cl_party_info si ON ((si.id = sp.info_id)))
                JOIN cl_party_info di ON ((di.id = dp.info_id)))
                LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01'
                AND s.action_id = 1 AND si.dn_type = 0 AND di.dn_type = 13 AND seq_order = 1
                AND si.dn != '1000' AND si.dn != '1001'
                GROUP BY si.dn
                ORDER BY si.dn ASC              
            )
            SELECT Call_out.Calls_by_Operator_out
            FROM Call_in
            INNER JOIN Call_out ON Call_in.Operator_ID_in = Call_out.Operator_ID_out
            INNER JOIN Canceled_calls ON Call_in.Operator_ID_in = Canceled_calls.ag_num
            """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        operator_id = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()
    list_to_str = ' '.join(map(str, operator_id))
    list_to_str = list_to_str.replace("(", "")
    list_to_str = list_to_str.replace(")", "")
    list_to_str = list_to_str.rstrip(list_to_str[-1])

    return list_to_str


def get_operator_cancel_calls():
    sql_request = (f"""
            WITH
            Canceled_calls AS (
                SELECT count (*) AS Call_count, ag_num
                FROM callcent_ag_dropped_calls
                WHERE time_start AT TIME ZONE 'UTC' > '2021-08-01' 
                AND reason_noanswerdesc != 'Answered' AND reason_noanswerdesc = 'Poll expired'
                AND ag_num != '1000' AND ag_num != '1001' AND ag_num != '9999'
                GROUP BY ag_num
                ORDER BY ag_num
            ),
            Call_in AS (
                SELECT to_dn AS Operator_ID_in, count (*) AS Calls_by_Operator_in
                FROM callcent_queuecalls
                WHERE ts_servicing != '00:00:00' AND time_start AT TIME ZONE 'UTC+3' > '2021-08-01' AND to_dn !=
                '1000' AND to_dn != '1001' AND to_dn != '9999'
                GROUP BY to_dn
                ORDER BY to_dn ASC
            ),
            Call_out AS (
                SELECT count (*) AS Calls_by_Operator_out, si.dn AS Operator_ID_out
                FROM ((((((cl_segments s
                JOIN cl_participants sp ON ((sp.id = s.src_part_id)))
                JOIN cl_participants dp ON ((dp.id = s.dst_part_id)))
                JOIN cl_party_info si ON ((si.id = sp.info_id)))
                JOIN cl_party_info di ON ((di.id = dp.info_id)))
                LEFT JOIN cl_participants ap ON ((ap.id = s.action_party_id)))
                LEFT JOIN cl_party_info ai ON ((ai.id = ap.info_id)))
                WHERE s.start_time AT TIME ZONE 'UTC-3' > '2021-08-01'
                AND s.action_id = 1 AND si.dn_type = 0 AND di.dn_type = 13 AND seq_order = 1
                AND si.dn != '1000' AND si.dn != '1001'
                GROUP BY si.dn
                ORDER BY si.dn ASC              
            )
            SELECT Canceled_calls.Call_count
            FROM Call_in
            INNER JOIN Call_out ON Call_in.Operator_ID_in = Call_out.Operator_ID_out
            INNER JOIN Canceled_calls ON Call_in.Operator_ID_in = Canceled_calls.ag_num
            """)

    try:
        connection = psycopg2.connect(database=database,
                                      user=user,
                                      password=password,
                                      host=host,
                                      port=port
                                      )

        cursor_call_count = connection.cursor()
        cursor_call_count.execute(str(sql_request))

        operator_id = cursor_call_count.fetchall()

    except (Exception, Error) as error:
        print("Ошибка при работе с PostgreSQL", error)

    finally:
        if connection:
            cursor_call_count.close()
            connection.close()
    list_to_str = ' '.join(map(str, operator_id))
    list_to_str = list_to_str.replace("(", "")
    list_to_str = list_to_str.replace(")", "")
    list_to_str = list_to_str.rstrip(list_to_str[-1])

    return list_to_str


def charts(request):
    operator_id = get_operator_id()
    calls_in = get_operator_in_calls()
    calls_out = get_operator_out_calls()
    calls_cancel = get_operator_cancel_calls()
    call_by_operator = render(request, 'cc_reports/charts.html', {'title': 'Звонки по операторам',
                                                                  'data_operator_id': operator_id,
                                                                  'data_calls_in': calls_in,
                                                                  'data_calls_out': calls_out,
                                                                  'data_calls_cancel': calls_cancel})
    return call_by_operator

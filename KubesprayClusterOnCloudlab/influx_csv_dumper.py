import argparse
import os
import csv
from influxdb import InfluxDBClient
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("-db", "--database", help="Database name", default="_internal", nargs='?')
parser.add_argument("-ip", "--hostname", help="Database address (ip/url)", default="localhost", nargs='?')
parser.add_argument("-p", "--port", help="Database port", default="8086", nargs='?')
parser.add_argument("-u", "--username", help="DB user name", default="root", nargs='?')
parser.add_argument("-pw", "--password", help="DB password", default="root", nargs='?')
parser.add_argument("-tl", "--timelength", help="Length of time for dump", default="1h", nargs='?')
parser.add_argument("-et", "--endtime", help="End time for dump", default='now()', nargs='?')
parser.add_argument("-f", "--filter", help="List of columns to filter", default='', nargs='?')
args = parser.parse_args()

host = args.hostname
port = args.port
username = args.username
password = args.password
dbname = args.database
time_length = args.timelength
end_time = args.endtime
filtered_str = args.filter
filtered = [x.strip() for x in filtered_str.split(',')]
client = InfluxDBClient(host, port, username, password, dbname)
#first we get list of all measurements in the selected db to dump them
query = 'show measurements'
result = client.query(query) 

for measurements in result:
    # print(measurements)
    for measure in measurements:
        # print(result)
        measure_name = measure['name']
        #get list of all fields for the measurement to build the CSV header
        names = ['time', 'readable_time']
        query = 'show tag keys from "'+measure_name+'"'
        fields_result = client.query(query)
        for field in fields_result:
            for pair in field:
                name = pair['tagKey']
                if name in filtered: continue
                names.append(name)
        query = 'show field keys from "'+measure_name+'"'
        fields_result = client.query(query)
        # print(query)
        for field in fields_result:
            for pair in field:
                name = pair['fieldKey']
                if name in filtered: continue
                names.append(name)
        
        print(names)
        
        filename = "report_csv/"+measure_name+'.csv'
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        #finally, request all data for all measurements in given timeframe and dump them as CSV rows to files
        with open(filename, 'w') as file:
            writer = csv.DictWriter(file, names, delimiter=',', lineterminator='\n', extrasaction='ignore')
            writer.writeheader()
            query = """select * from "{}" where time > {} - {} AND time < {} """.format(measure_name, end_time, time_length, end_time)
            print(query)
            #https://docs.influxdata.com/influxdb/v0.13/guides/querying_data/
            result = client.query(query, epoch='ms')
            for point in result:
                for item in point:
                    ms = item['time'] / 1000
                    d = datetime.fromtimestamp(ms)
                    item['readable_time'] = d.isoformat('T')+'Z'
                    writer.writerow(item)

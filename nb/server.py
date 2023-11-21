import grpc
import station_pb2_grpc, station_pb2
from concurrent import futures
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel

class ModelServer(station_pb2_grpc.StationServicer):

    cluster = Cluster(['p6-db-1', 'p6-db-2', 'p6-db-3'])
    cass = cluster.connect('weather')
    insert_statement = cass.prepare("""
    INSERT INTO stations (id, data, record)
    VALUES (?, ?, ?)
    """)
    insert_statement.consistency_level = ConsistencyLevel.ONE
    max_statement = cass.prepare("""
    SELECT MAX(tmax) FROM stations WHERE id = ?
    """)
    max_statement.consistency_level = ConsistencyLevel.ONE
    
    def RecordTemps(self, request, context):
        try:
            cluster.register_user_type('stations', 'record', Record)
            record = { 'tmin': request.tmin, 'tmax':request.tmax }
            cass.execute(insert_statement, (Record(request.station, request.date, record)))
            return station_pb2.RecordTempsReply(error = "")
        except Unavailable as e:
            return station_pb2.RecordTempsReply(error= f'need {e.required_replicas} replicas, but only have {e.alive_replicas}')
        except NoHostAvailable as e:
            for evalue in e.errors.values():
                return station_pb2.RecordTempsReply(error= f'need {evalue.required_replicas} replicas, but only have {evalue.alive_replicas}')
        except Exception as e:
            return station_pb2.RecordTempsReply(error=str(e))
            
    def StationMax(self, request, context):
        try:
            result = cass.execute(max_statement, (request.station, ))
            row = result.one()
            if row:
                return station_pb2.StationMaxReply(tmax = row[0], error=str(e))
            else:
                return station_pb2.RecordTempsReply(tmax = 0, error= "No data")
        except Unavailable as e:
            return station_pb2.RecordTempsReply(tmax = 0, error= f'need {e.required_replicas} replicas, but only have {e.alive_replicas}')
        except NoHostAvailable as e:
            for evalue in e.errors.values():
                return station_pb2.RecordTempsReply(tmax = 0, error= f'need {evalue.required_replicas} replicas, but only have {evalue.alive_replicas}')
        except Exception as e:
            return station_pb2.RecordTempsReply(tmax = 0, error=str(e))
            
if __name__ == '__main__':
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4), options=(('grpc.so_reuseport', 0),))
    station_pb2_grpc.add_ModelServerServicer_to_server(ModelServer(), server)
    server.add_insecure_port("[::]:5440", )
    server.start()
    print("started")
    server.wait_for_termination()
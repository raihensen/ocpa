import json
from typing import Dict, List, Any, Union

import pandas as pd
from datetime import datetime
from collections import OrderedDict

from ocpa.objects.log.importer.ocel.parameters import JsonParseParameters
from ocpa.objects.log.variants.obj import Event, Obj, ObjectCentricEventLog, MetaObjectCentricData, RawObjectCentricData
from ocpa.objects.log.obj import OCEL
import ocpa.objects.log.converter.factory as convert_factory
from ocpa.objects.log.variants.table import Table
from ocpa.objects.log.variants.graph import EventGraph
import ocpa.objects.log.variants.util.table as table_utils


def apply(filepath, parameters: Dict, file_path_object_attribute_table=None) -> OCEL:
    if parameters is None:
        parameters = {}
    obj = import_jsonocel(filepath)
    df, _ = convert_factory.apply(obj, variant='json_to_csv')
    obj_df = None
    if(file_path_object_attribute_table):
        obj_df = pd.read_csv(file_path_object_attribute_table)
    table_parameters = {"obj_names": obj.meta.obj_types,
                        # TODO check this in a future release
                        # "val_names": obj.meta.attr_types,
                        "val_names": ['event_'.join(name) for name in obj.meta.attr_events],
                        "act_name": "event_activity",
                        "time_name": "event_timestamp",
                        "sep": ","}
    table_parameters.update(parameters)
    # TODO see here
    # print(table_parameters)
    log = Table(df, parameters=table_parameters, object_attributes=obj_df)
    graph = EventGraph(table_utils.eog_from_log(log))
    ocel = OCEL(log, obj, graph, table_parameters)
    return ocel


def import_jsonocel(file_path, parameters=None) -> ObjectCentricEventLog:
    F = open(file_path, "rb")
    obj = json.load(F)
    F.close()
    return parse_json(obj)


def parse_json(data: Dict[str, Any]) -> ObjectCentricEventLog:
    cfg = JsonParseParameters()
    # parses the given dict
    events, obj_event_mapping = parse_events(
        data[cfg.log_params['events']], cfg)
    objects = parse_objects(data[cfg.log_params['objects']], cfg)
    # Uses the last found value type
    attr_events = {v:
                   str(type(events[eid].vmap[v])) for eid in events
                   for v in events[eid].vmap}
    attr_objects = {v:
                    str(type(objects[oid].ovmap[v])) for oid in objects
                    for v in objects[oid].ovmap
                    }
    attr_types = list({attr_events[v] for v in attr_events}.union(
        {attr_objects[v] for v in attr_objects}))
    attr_typ = {**attr_events, **attr_objects}
    act_attr = {}
    for eid, event in events.items():
        act = event.act
        if act not in act_attr:
            act_attr[act] = {v for v in event.vmap}
        else:
            act_attr[act] = act_attr[act].union({v for v in event.vmap})
    for act in act_attr:
        act_attr[act] = list(act_attr[act])
    meta = MetaObjectCentricData(attr_names=data[cfg.log_params['meta']][cfg.log_params['attr_names']],
                                 obj_types=data[cfg.log_params['meta']
                                                ][cfg.log_params['obj_types']],
                                 attr_types=attr_types,
                                 attr_typ=attr_typ,
                                 act_attr=act_attr,
                                 attr_events=list(attr_events.keys()))
    data = ObjectCentricEventLog(
        meta, RawObjectCentricData(events, objects, obj_event_mapping))
    return data


def parse_events(data: Dict[str, Any], cfg: JsonParseParameters) -> Dict[str, Event]:
    # Transform events dict to list of events
    act_name = cfg.event_params['act']
    omap_name = cfg.event_params['omap']
    vmap_name = cfg.event_params['vmap']
    time_name = cfg.event_params['time']
    events = {}
    obj_event_mapping = {}
    eid = 0
    for item in data.items():
        events[eid] = Event(id=eid,
                            act=item[1][act_name],
                            omap=item[1][omap_name],
                            vmap=item[1][vmap_name],
                            time=datetime.fromisoformat(item[1][time_name]))
        if "start_timestamp" not in item[1][vmap_name]:
            events[eid].vmap["start_timestamp"] = datetime.fromisoformat(
                item[1][time_name])
        else:
            events[eid].vmap["start_timestamp"] = datetime.fromisoformat(
                events[eid].vmap["start_timestamp"])

        for oid in item[1][omap_name]:
            if oid in obj_event_mapping:
                obj_event_mapping[oid].append(eid)
            else:
                obj_event_mapping[oid] = [eid]
        eid += 1

    sorted_events = sorted(events.items(), key=lambda kv: kv[1].time)
    return OrderedDict(sorted_events), obj_event_mapping


def parse_objects(data: Dict[str, Any], cfg: JsonParseParameters) -> Dict[str, Obj]:
    # Transform objects dict to list of objects
    type_name = cfg.obj_params['type']
    ovmap_name = cfg.obj_params['ovmap']
    objects = {item[0]: Obj(id=item[0],
                            type=item[1][type_name],
                            ovmap=item[1][ovmap_name])
               for item in data.items()}
    return objects

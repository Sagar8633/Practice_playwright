-- =====================================================================
-- Analytics Manager - PRACTICE SEED DATA
-- =====================================================================
-- Deliberately dirty. Every anomaly below is PLANTED so that a specific
-- family of QA exercises has something real to find. Do not "clean" it.
--
--  A1  Orphan events        ~220 events whose "VideoSourceId" points at
--                           three cameras that no longer exist (GAP #1).
--  A2  NULL camera events   ~70 events with "VideoSourceId" IS NULL, so
--                           NOT IN (SELECT ...) genuinely returns nothing.
--  A3  Silent camera        PERIM-North-07 stops emitting after day 19.
--  A4  Volume drop          ANPR-Gate-01 falls to ~30% yesterday.
--  A5  Clock skew           LOBBY-Main-12 reports Time AHEAD of ReceivedTime
--                           -> negative ingestion latency.
--  A6  Ingest lag           HW-Median-21 has 45-90 s latency, not ~1 s.
--  A7  Duplicate TrackId    FACE-Entry-03 emits a burst sharing TrackIds
--                           with identical "Time" (GAP #6).
--  A8  Low confidence       FACE-Lobby-18 sits below RecognitionConfidence.
--  A9  Exact tie            Two cameras are forced to identical event
--                           totals, so RANK <> ROW_NUMBER is observable.
--  A10 Future events        A few events dated after now().
--  A11 Dangling activeConfigId  (GAP #2)  SAFETY-Paint-40.
--  A12 configurationsAdded lie  LOBBY-Atrium-39 flagged true, no config row.
--  A13 Orphan server        AS-ORPHAN-01 references a missing manager (GAP #4).
--  A14 Role drift           One user's "RoleId" disagrees with AspNetUserRoles
--                           (GAP #5).
--  A15 Over-capacity        PL-Face-Bank-A exceeds MaxVideoSourceAllowed.
--  A16 Mapping drift        AnalyticServerDeviceMapping vs PipeLineVideoSources
--                           disagree on three cameras.
--  A17 Stale external src   VMS-Genetec-North last synced ~45 days ago.
--  A18 Missing snapshots    A slice of events has "SnapshotPath" IS NULL.
--  A19 Stream gap           FACE-Server-Room-32 uses StreamType 2 but has no
--                           row for it in VideoSourceStreamMappings.
--  A20 Dangling ScheduleId  Every VideoSourceConfigs row (GAP #3, structural).
--
-- Timeline: 30 full days ending YESTERDAY, plus a partial "today".
-- =====================================================================

SELECT setseed(0.4242);

-- ---------------------------------------------------------------------
-- Analytic managers
-- ---------------------------------------------------------------------
INSERT INTO public."AnalyticManagers"
    ("Id","Name","keyValuePairs","ManagerIp","ManagerPort","RabbitMQIp","RabbitMQPort",
     "RabbitMqUserName","RabbitMqUserPassword","IsAnlayticManagerConnected")
VALUES
    (md5('am-central')::uuid,   'AM-Central',
     '{"site":"HQ","tz":"Asia/Kolkata","gpuCount":4}'::jsonb,
     '192.168.7.10', 5000, '192.168.7.10', 5672, 'amqadmin', 'enc:9f2a', true),
    (md5('am-north')::uuid,     'AM-Edge-North',
     '{"site":"Plant-North","tz":"Asia/Kolkata","gpuCount":1}'::jsonb,
     '192.168.7.44', 5000, '192.168.7.44', 5672, 'amqadmin', 'enc:1c7d', true),
    (md5('am-south')::uuid,     'AM-Edge-South',
     '{"site":"Plant-South","tz":"Asia/Kolkata","gpuCount":1}'::jsonb,
     '192.168.7.61', 5000, '192.168.7.61', 5672, 'amqadmin', NULL, false);

-- ---------------------------------------------------------------------
-- External sources (VMS / NVR).  A17: one is badly stale.
-- ---------------------------------------------------------------------
INSERT INTO public."ExternalSources"
    ("Id","Name","Type","Ip","Port","FailoverIp","LastSynced","ServerState")
VALUES
    (md5('ext-milestone')::uuid, 'VMS-Milestone-HQ', 1, '192.168.7.80', 80,
     '192.168.7.81', now() - interval '12 minutes', 0),
    (md5('ext-genetec')::uuid,   'VMS-Genetec-North', 2, '192.168.7.82', 443,
     NULL,          now() - interval '45 days', 2),
    (md5('ext-hik')::uuid,       'NVR-Hikvision-South', 3, '192.168.7.83', 8000,
     '192.168.7.84', now() - interval '3 hours', 1),
    (md5('ext-onvif')::uuid,     'ONVIF-Direct', 0, '192.168.7.85', 8899,
     NULL,          now() - interval '2 days', 0);

-- ---------------------------------------------------------------------
-- Analytic servers.  A13: AS-ORPHAN-01 has a manager id that does not exist.
-- ---------------------------------------------------------------------
INSERT INTO public."AnalyticServers"
    ("Id","Name","Ip","RestPort","AlertListeningPort","AnalyticManagerId","Type",
     "AlertListeningIp","AlertListeningType","StreamingPort","FailoverServerId","IsFailoverOnly")
VALUES
    (md5('as-failover-1')::uuid,'AS-FAILOVER-01','192.168.7.50',7018,7020,md5('am-central')::uuid,1,'192.168.7.50',0,7093,NULL,true),
    (md5('as-gpu-1')::uuid,     'AS-GPU-01',     '192.168.7.44',7018,7020,md5('am-central')::uuid,0,'192.168.7.44',0,7093,md5('as-failover-1')::uuid,false),
    (md5('as-gpu-2')::uuid,     'AS-GPU-02',     '192.168.7.45',7018,7020,md5('am-central')::uuid,0,'192.168.7.45',0,7093,md5('as-failover-1')::uuid,false),
    (md5('as-gpu-3')::uuid,     'AS-GPU-03',     '192.168.7.46',7018,7020,md5('am-north')::uuid,  0,'192.168.7.46',1,7093,NULL,false),
    (md5('as-gpu-4')::uuid,     'AS-GPU-04',     '192.168.7.47',7018,7020,md5('am-north')::uuid,  0,'192.168.7.47',1,NULL,NULL,false),
    (md5('as-gpu-5')::uuid,     'AS-GPU-05',     '192.168.7.48',7018,7020,md5('am-south')::uuid,  2,'192.168.7.48',0,7093,NULL,false),
    (md5('as-orphan-1')::uuid,  'AS-ORPHAN-01',  '192.168.7.99',7018,7020,md5('am-decommissioned')::uuid,0,'192.168.7.99',0,NULL,NULL,false);

-- ---------------------------------------------------------------------
-- Video sources (40 cameras)
--   base daily rate = 10 + ((i*13) % 41)  -> 40 DISTINCT rates, no accidental ties
--   A11 camera 40 has a dangling activeConfigId
--   A12 camera 39 claims configurationsAdded with no config row
-- ---------------------------------------------------------------------
INSERT INTO public."VideoSources"
    ("Id","Name","ProcessingWidth","ProcessingHeight","Ip","AnalyticManagerId",
     "configurationsAdded","activeConfigId","Snapshot","ExternalSourceType",
     "ExternalVideoSourceId","ExternalSourceId","UseStreamType")
SELECT
    md5('cam-'||i)::uuid,
    n.names[i],
    (ARRAY[1920,1280,2688,1920])[1+(i%4)],
    (ARRAY[1080, 720,1520,1080])[1+(i%4)],
    '192.168.7.'||(100+i),
    CASE WHEN i <= 18 THEN md5('am-central')::uuid
         WHEN i <= 31 THEN md5('am-north')::uuid
         ELSE md5('am-south')::uuid END,
    CASE WHEN i = 39 THEN true                    -- A12: lies
         WHEN i IN (33,36) THEN false             -- genuinely unconfigured
         ELSE true END,
    CASE WHEN i = 40 THEN md5('cfg-vanished')::uuid   -- A11: dangling
         ELSE md5('cfg-'||i)::uuid END,
    CASE WHEN i % 7 = 0 THEN NULL
         ELSE '/snapshots/cam-'||i||'/latest.jpg' END,
    CASE WHEN i % 3 = 0 THEN 1 ELSE NULL END,
    CASE WHEN i % 3 = 0 THEN 'ext-dev-'||(1000+i) ELSE NULL END,
    CASE WHEN i % 3 = 0 THEN md5('ext-milestone')::uuid ELSE NULL END,
    CASE WHEN i = 32 THEN 2                       -- A19: no StreamType 2 mapping exists
         WHEN i % 5 = 0 THEN 1
         ELSE 0 END
FROM generate_series(1,40) AS i,
LATERAL (SELECT ARRAY[
    'ANPR-Gate-01','ANPR-Gate-02','FACE-Entry-03','PERIM-East-04','SAFETY-Plant-05',
    'HW-Median-06','PERIM-North-07','ANPR-Toll-08','FIRE-Yard-09','FACE-Turnstile-10',
    'PERIM-West-11','LOBBY-Main-12','SAFETY-Weld-13','HW-Ramp-14','ANPR-Exit-15',
    'FIRE-Store-16','FACE-Gate-17','FACE-Lobby-18','PERIM-South-19','SAFETY-Crane-20',
    'HW-Median-21','ANPR-Gate-22','LOBBY-Rear-23','FIRE-Dock-24','PERIM-Fence-25',
    'FACE-Cafeteria-26','SAFETY-Loading-27','HW-Bridge-28','ANPR-Weighbridge-29','LOBBY-Side-30',
    'PERIM-Gate-31','FACE-Server-Room-32','SAFETY-Chem-33','HW-Tunnel-34','ANPR-Parking-35',
    'FIRE-Genset-36','PERIM-Roof-37','FACE-Reception-38','LOBBY-Atrium-39','SAFETY-Paint-40'
    ] AS names) n;

-- ---------------------------------------------------------------------
-- Video source configs.  A20: every ScheduleId dangles - no Schedules table.
--   camera 39 deliberately gets none;  cameras 5,12,20 get a second,
--   NON-active config so "which config is live" needs activeConfigId.
-- ---------------------------------------------------------------------
INSERT INTO public."VideoSourceConfigs"
    ("Id","ANPRParams","BasicParams","VideoSourceId","DisabledRules","AppliedRules","ScheduleId")
SELECT
    md5('cfg-'||i)::uuid,
    CASE WHEN n.names[i] LIKE 'ANPR%'
         THEN '{"plateMinHeight":22,"country":"IN","ocrModel":"lpr_v4"}' ELSE NULL END,
    '{"fps":'||(4+(i%6))||',"roiCount":'||(1+(i%3))||',"decoder":"GPU"}',
    md5('cam-'||i)::uuid,
    CASE WHEN i % 6 = 0 THEN 'Camera_Tampered' ELSE NULL END,
    CASE
      WHEN n.names[i] LIKE 'ANPR%'   THEN ARRAY['ANPR','Speed_Detected','Wrong_Way_Detected']
      WHEN n.names[i] LIKE 'FACE%'   THEN ARRAY['Face_Recognition']
      WHEN n.names[i] LIKE 'PERIM%'  THEN ARRAY['Intrusion_Detected','Perimeter_Violation','Human_Detected']
      WHEN n.names[i] LIKE 'SAFETY%' THEN ARRAY['Safety_Gear_Violation','Person_Fallen','Human_Pose_Detection']
      WHEN n.names[i] LIKE 'HW%'     THEN ARRAY['Highway_ATCC','Congestion_Detected','Traffic_Analyzer']
      WHEN n.names[i] LIKE 'FIRE%'   THEN ARRAY['Fire_Detected','Smoke_Detected']
      ELSE ARRAY['Motion_Detected','Human_Detected','Crowd_Detected']
    END,
    md5('sched-'||(1+(i%4)))::uuid
FROM generate_series(1,40) AS i,
LATERAL (SELECT ARRAY[
    'ANPR-Gate-01','ANPR-Gate-02','FACE-Entry-03','PERIM-East-04','SAFETY-Plant-05',
    'HW-Median-06','PERIM-North-07','ANPR-Toll-08','FIRE-Yard-09','FACE-Turnstile-10',
    'PERIM-West-11','LOBBY-Main-12','SAFETY-Weld-13','HW-Ramp-14','ANPR-Exit-15',
    'FIRE-Store-16','FACE-Gate-17','FACE-Lobby-18','PERIM-South-19','SAFETY-Crane-20',
    'HW-Median-21','ANPR-Gate-22','LOBBY-Rear-23','FIRE-Dock-24','PERIM-Fence-25',
    'FACE-Cafeteria-26','SAFETY-Loading-27','HW-Bridge-28','ANPR-Weighbridge-29','LOBBY-Side-30',
    'PERIM-Gate-31','FACE-Server-Room-32','SAFETY-Chem-33','HW-Tunnel-34','ANPR-Parking-35',
    'FIRE-Genset-36','PERIM-Roof-37','FACE-Reception-38','LOBBY-Atrium-39','SAFETY-Paint-40'
    ] AS names) n
WHERE i <> 39;   -- A12

INSERT INTO public."VideoSourceConfigs"
    ("Id","ANPRParams","BasicParams","VideoSourceId","DisabledRules","AppliedRules","ScheduleId")
SELECT md5('cfg2-'||i)::uuid, NULL,
       '{"fps":2,"roiCount":1,"decoder":"CPU","note":"night profile"}',
       md5('cam-'||i)::uuid, NULL, ARRAY['Motion_Detected'],
       md5('sched-night')::uuid
FROM unnest(ARRAY[5,12,20]) AS i;

-- ---------------------------------------------------------------------
-- Stream mappings.  A19: camera 32 uses StreamType 2 but gets no row for it.
-- ---------------------------------------------------------------------
INSERT INTO public."VideoSourceStreamMappings" ("Id","VideoSourceId","StreamType","Url")
SELECT md5('sm-main-'||i)::uuid, md5('cam-'||i)::uuid, 0,
       'rtsp://admin:admin@192.168.7.'||(100+i)||':8801/main'
FROM generate_series(1,40) AS i;

INSERT INTO public."VideoSourceStreamMappings" ("Id","VideoSourceId","StreamType","Url")
SELECT md5('sm-sub-'||i)::uuid, md5('cam-'||i)::uuid, 1,
       'rtsp://admin:admin@192.168.7.'||(100+i)||':8801/sub'
FROM generate_series(1,40) AS i
WHERE i % 2 = 0;

-- ---------------------------------------------------------------------
-- A21  Two brand-new cameras: fully and correctly configured, assigned to
--      a pipeline, placed on a server -- and they have never emitted a
--      single event. This is what a camera commissioned but never started
--      looks like, and it is invisible to every report built FROM Events.
-- ---------------------------------------------------------------------
INSERT INTO public."VideoSources"
    ("Id","Name","ProcessingWidth","ProcessingHeight","Ip","AnalyticManagerId",
     "configurationsAdded","activeConfigId","Snapshot","ExternalSourceType",
     "ExternalVideoSourceId","ExternalSourceId","UseStreamType")
VALUES
    (md5('cam-41')::uuid,'PERIM-NewWing-41',1920,1080,'192.168.7.141',
     md5('am-north')::uuid,true,md5('cfg-41')::uuid,NULL,NULL,NULL,NULL,0),
    (md5('cam-42')::uuid,'FACE-NewWing-42',1920,1080,'192.168.7.142',
     md5('am-north')::uuid,true,md5('cfg-42')::uuid,NULL,NULL,NULL,NULL,0);

INSERT INTO public."VideoSourceConfigs"
    ("Id","ANPRParams","BasicParams","VideoSourceId","DisabledRules","AppliedRules","ScheduleId")
VALUES
    (md5('cfg-41')::uuid,NULL,'{"fps":6,"roiCount":1,"decoder":"GPU"}',
     md5('cam-41')::uuid,NULL,ARRAY['Intrusion_Detected','Perimeter_Violation'],md5('sched-1')::uuid),
    (md5('cfg-42')::uuid,NULL,'{"fps":6,"roiCount":1,"decoder":"GPU"}',
     md5('cam-42')::uuid,NULL,ARRAY['Face_Recognition'],md5('sched-1')::uuid);

INSERT INTO public."VideoSourceStreamMappings" ("Id","VideoSourceId","StreamType","Url")
VALUES
    (md5('sm-main-41')::uuid, md5('cam-41')::uuid, 0,'rtsp://admin:admin@192.168.7.141:8801/main'),
    (md5('sm-main-42')::uuid, md5('cam-42')::uuid, 0,'rtsp://admin:admin@192.168.7.142:8801/main');

-- ---------------------------------------------------------------------
-- Pipelines.  A15: PL-Face-Bank-A is deliberately over capacity.
-- ---------------------------------------------------------------------
INSERT INTO public."PipeLines" ("Id","Name","Type","MaxVideoSourceAllowed","AnalyticServerId","Enabled")
VALUES
    (md5('pl-anpr-a')::uuid,   'PL-ANPR-A',      1, 8, md5('as-gpu-1')::uuid, true),
    (md5('pl-anpr-b')::uuid,   'PL-ANPR-B',      1, 8, md5('as-gpu-2')::uuid, true),
    (md5('pl-face-a')::uuid,   'PL-Face-Bank-A', 2, 4, md5('as-gpu-1')::uuid, true),
    (md5('pl-face-b')::uuid,   'PL-Face-Bank-B', 2, 6, md5('as-gpu-3')::uuid, true),
    (md5('pl-perim-a')::uuid,  'PL-Perimeter-A', 3,10, md5('as-gpu-2')::uuid, true),
    (md5('pl-perim-b')::uuid,  'PL-Perimeter-B', 3,10, md5('as-gpu-4')::uuid, false),
    (md5('pl-safety-a')::uuid, 'PL-Safety-A',    4, 8, md5('as-gpu-3')::uuid, true),
    (md5('pl-safety-b')::uuid, 'PL-Safety-B',    4, 8, md5('as-gpu-5')::uuid, false),
    (md5('pl-hw-a')::uuid,     'PL-Highway-A',   5, 6, md5('as-gpu-4')::uuid, true),
    (md5('pl-fire-a')::uuid,   'PL-Fire-A',      6, 6, md5('as-gpu-5')::uuid, true),
    (md5('pl-lobby-a')::uuid,  'PL-Lobby-A',     0,12, md5('as-gpu-2')::uuid, true),
    (md5('pl-spare-a')::uuid,  'PL-Spare-Unused',0, 4, md5('as-failover-1')::uuid, true);

INSERT INTO public."PipeLineConfigs" ("Id","Key","Value","PipeLineId","Type","ConfigType","BlockName")
SELECT md5('plc-'||p.k||'-'||c.key)::uuid, c.key, c.val, md5(p.k)::uuid, 0, 1, 'inference'
FROM (VALUES ('pl-anpr-a'),('pl-anpr-b'),('pl-face-a'),('pl-face-b'),('pl-perim-a'),
             ('pl-perim-b'),('pl-safety-a'),('pl-safety-b'),('pl-hw-a'),('pl-fire-a'),
             ('pl-lobby-a'),('pl-spare-a')) AS p(k),
     (VALUES ('batchSize','4'),('model','Person_60'),('backend','nvidia_full0'),
             ('processingInterval','4')) AS c(key,val);

-- ---------------------------------------------------------------------
-- Pipeline <-> camera assignment (N:M).  A15 over-capacity on PL-Face-Bank-A.
--   Cameras 33 and 36 are deliberately assigned to NO pipeline.
-- ---------------------------------------------------------------------
INSERT INTO public."PipeLineVideoSources" ("Id","PipeLineId","VideoSourceId")
SELECT md5('plvs-'||i)::uuid,
       CASE
         WHEN n.names[i] LIKE 'ANPR%'   AND i <= 15 THEN md5('pl-anpr-a')::uuid
         WHEN n.names[i] LIKE 'ANPR%'                THEN md5('pl-anpr-b')::uuid
         WHEN n.names[i] LIKE 'FACE%'   AND i <= 26 THEN md5('pl-face-a')::uuid
         WHEN n.names[i] LIKE 'FACE%'                THEN md5('pl-face-b')::uuid
         WHEN n.names[i] LIKE 'PERIM%'  AND i <= 25 THEN md5('pl-perim-a')::uuid
         WHEN n.names[i] LIKE 'PERIM%'               THEN md5('pl-perim-b')::uuid
         WHEN n.names[i] LIKE 'SAFETY%' AND i <= 27 THEN md5('pl-safety-a')::uuid
         WHEN n.names[i] LIKE 'SAFETY%'              THEN md5('pl-safety-b')::uuid
         WHEN n.names[i] LIKE 'HW%'                  THEN md5('pl-hw-a')::uuid
         WHEN n.names[i] LIKE 'FIRE%'                THEN md5('pl-fire-a')::uuid
         ELSE md5('pl-lobby-a')::uuid
       END,
       md5('cam-'||i)::uuid
FROM generate_series(1,40) AS i,
LATERAL (SELECT ARRAY[
    'ANPR-Gate-01','ANPR-Gate-02','FACE-Entry-03','PERIM-East-04','SAFETY-Plant-05',
    'HW-Median-06','PERIM-North-07','ANPR-Toll-08','FIRE-Yard-09','FACE-Turnstile-10',
    'PERIM-West-11','LOBBY-Main-12','SAFETY-Weld-13','HW-Ramp-14','ANPR-Exit-15',
    'FIRE-Store-16','FACE-Gate-17','FACE-Lobby-18','PERIM-South-19','SAFETY-Crane-20',
    'HW-Median-21','ANPR-Gate-22','LOBBY-Rear-23','FIRE-Dock-24','PERIM-Fence-25',
    'FACE-Cafeteria-26','SAFETY-Loading-27','HW-Bridge-28','ANPR-Weighbridge-29','LOBBY-Side-30',
    'PERIM-Gate-31','FACE-Server-Room-32','SAFETY-Chem-33','HW-Tunnel-34','ANPR-Parking-35',
    'FIRE-Genset-36','PERIM-Roof-37','FACE-Reception-38','LOBBY-Atrium-39','SAFETY-Paint-40'
    ] AS names) n
WHERE i NOT IN (33,36);

-- The two new cameras are properly assigned, so their only anomaly is silence.
INSERT INTO public."PipeLineVideoSources" ("Id","PipeLineId","VideoSourceId")
VALUES (md5('plvs-41')::uuid, md5('pl-perim-a')::uuid, md5('cam-41')::uuid),
       (md5('plvs-42')::uuid, md5('pl-face-b')::uuid,  md5('cam-42')::uuid);

-- ---------------------------------------------------------------------
-- Runtime placement.  A16: three deliberate drifts from PipeLineVideoSources.
-- ---------------------------------------------------------------------
INSERT INTO public."AnalyticServerDeviceMapping"
    ("Id","AnalyticServerId","VideoSourceId","PipelineId","AnalyticManagerId","PipelineType")
SELECT md5('asdm-'||v."VideoSourceId"::text)::uuid,
       p."AnalyticServerId", v."VideoSourceId", v."PipeLineId",
       vs."AnalyticManagerId", p."Type"
FROM public."PipeLineVideoSources" v
JOIN public."PipeLines"    p  ON p."Id"  = v."PipeLineId"
JOIN public."VideoSources" vs ON vs."Id" = v."VideoSourceId"
WHERE v."VideoSourceId" NOT IN (md5('cam-7')::uuid, md5('cam-18')::uuid);  -- A16: mapped to a pipeline, but never placed

INSERT INTO public."AnalyticServerDeviceMapping"
    ("Id","AnalyticServerId","VideoSourceId","PipelineId","AnalyticManagerId","PipelineType")
VALUES  -- A16: placed on a server, but absent from PipeLineVideoSources
    (md5('asdm-ghost-33')::uuid, md5('as-gpu-3')::uuid, md5('cam-33')::uuid, NULL, md5('am-south')::uuid, NULL);

-- ---------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------
INSERT INTO public."AspNetRoles" ("Id","Name","NormalizedName","ConcurrencyStamp") VALUES
    (md5('role-admin')::uuid,   'Administrator','ADMINISTRATOR', md5('cs1')),
    (md5('role-operator')::uuid,'Operator',     'OPERATOR',      md5('cs2')),
    (md5('role-viewer')::uuid,  'Viewer',       'VIEWER',        md5('cs3')),
    (md5('role-auditor')::uuid, 'Auditor',      'AUDITOR',       md5('cs4'));

INSERT INTO public."AspNetUsers"
    ("Id","Preferences","ProfileImagePath","RoleId","UserName","NormalizedUserName","Email",
     "NormalizedEmail","EmailConfirmed","PasswordHash","SecurityStamp","ConcurrencyStamp",
     "PhoneNumber","PhoneNumberConfirmed","TwoFactorEnabled","LockoutEnd","LockoutEnabled",
     "LoginWindow","AccessFailedCount")
SELECT
    md5('user-'||i)::uuid,
    CASE WHEN i % 3 = 0 THEN NULL ELSE '{"theme":"dark","pageSize":50}' END,
    CASE WHEN i % 4 = 0 THEN NULL ELSE '/avatars/u'||i||'.png' END,
    (ARRAY[md5('role-admin')::uuid, md5('role-operator')::uuid, md5('role-operator')::uuid,
           md5('role-viewer')::uuid, md5('role-viewer')::uuid,  md5('role-auditor')::uuid,
           md5('role-operator')::uuid, md5('role-viewer')::uuid, md5('role-operator')::uuid,
           md5('role-viewer')::uuid])[i],
    u.unames[i], upper(u.unames[i]),
    u.unames[i]||'@analytics.local', upper(u.unames[i]||'@ANALYTICS.LOCAL'),
    (i % 5 <> 0),
    'AQAAAAEAACcQAAAAE'||md5('pw'||i),
    md5('ss'||i), md5('cc'||i),
    CASE WHEN i % 3 = 0 THEN NULL ELSE '+9198'||(10000000+i*137) END,
    (i % 4 = 0), (i = 1),
    CASE WHEN i = 8 THEN now() + interval '2 days' ELSE NULL END,
    true, true,
    CASE WHEN i = 8 THEN 5 WHEN i = 4 THEN 2 ELSE 0 END
FROM generate_series(1,10) AS i,
LATERAL (SELECT ARRAY['admin','r.sharma','p.nair','a.patel','s.rao',
                      'v.singh','a.desai','k.mehta','d.iyer','n.gupta'] AS unames) u;

-- Role junction.  A14: user 'k.mehta' (i=8) has RoleId=Viewer on the row,
-- but the junction says Operator -> the two sources of truth disagree.
INSERT INTO public."AspNetUserRoles" ("UserId","RoleId")
SELECT md5('user-'||i)::uuid,
       CASE WHEN i = 8 THEN md5('role-operator')::uuid
            ELSE (ARRAY[md5('role-admin')::uuid, md5('role-operator')::uuid, md5('role-operator')::uuid,
                        md5('role-viewer')::uuid, md5('role-viewer')::uuid,  md5('role-auditor')::uuid,
                        md5('role-operator')::uuid, md5('role-viewer')::uuid, md5('role-operator')::uuid,
                        md5('role-viewer')::uuid])[i] END
FROM generate_series(1,10) AS i
WHERE i <> 10;   -- user 'n.gupta' has a RoleId but NO junction row at all

INSERT INTO public."AspNetRoleClaims" ("RoleId","ClaimType","ClaimValue")
SELECT md5('role-admin')::uuid, 'Rights', c
FROM unnest(ARRAY['ShowAnalyticServerTab','AddAnalyticServer','EditAnalyticServer','DeleteAnalyticServer',
                  'AddPipeline','EditPipeline','DeletePipeline','StartPipeline',
                  'AttachVideoSourceToServerOrPipeline','ShowVideoSourceTab','AddVideoSource',
                  'EditVideoSource','DeleteVideoSource','AddConfigurationsToVideoSource',
                  'ShowEventsTab','AddRules','EditRulesOrActions','DeleteRules',
                  'ShowConfigurationsTab','EditConfigurations','ShowNotificationsTab',
                  'ShowUsersTab','AddUser','EditUser','DeleteUser','ShowWatchlistTab',
                  'ViewCameraFeed','ReportRights','ExportReportData','ShowVMSTab']) AS c;

INSERT INTO public."AspNetRoleClaims" ("RoleId","ClaimType","ClaimValue")
SELECT md5('role-operator')::uuid, 'Rights', c
FROM unnest(ARRAY['ShowVideoSourceTab','ShowEventsTab','ViewCameraFeed','ShowConfigurationsTab',
                  'EditConfigurations','ReportRights','ShowNormalReport']) AS c;

INSERT INTO public."AspNetRoleClaims" ("RoleId","ClaimType","ClaimValue")
SELECT md5('role-viewer')::uuid, 'Rights', c
FROM unnest(ARRAY['ShowEventsTab','ViewCameraFeed','ShowNormalReport']) AS c;

INSERT INTO public."AspNetRoleClaims" ("RoleId","ClaimType","ClaimValue")
SELECT md5('role-auditor')::uuid, 'Rights', c
FROM unnest(ARRAY['ShowEventsTab','ReportRights','ExportReportData','ShowPeopleReport',
                  'ShowAttendanceReport']) AS c;

INSERT INTO public."AspNetUserClaims" ("Id","UserId","ClaimType","ClaimValue")
SELECT md5('uc-'||i)::uuid, md5('user-'||i)::uuid, 'Site',
       CASE WHEN i % 3 = 0 THEN 'Plant-North' ELSE 'HQ' END
FROM generate_series(1,10) AS i WHERE i % 2 = 1;

INSERT INTO public."AspNetUserLogins" ("LoginProvider","ProviderKey","ProviderDisplayName","UserId")
VALUES ('AzureAD','azad|k.mehta','Azure Active Directory', md5('user-8')::uuid),
       ('AzureAD','azad|d.iyer', 'Azure Active Directory', md5('user-9')::uuid);

INSERT INTO public."AspNetUserTokens" ("UserId","LoginProvider","Name","Value")
VALUES (md5('user-1')::uuid,'Default','RefreshToken', md5('tok1')),
       (md5('user-2')::uuid,'Default','RefreshToken', md5('tok2'));

-- Per-user camera ACL.  Users 4,5,10 (viewers) get narrow slices;
-- user 6 (auditor) gets none at all.
-- Note the admins stop at camera 34: the highest-numbered cameras were added
-- later and nobody extended the access grants. Cameras 36, 37 and 38 end up
-- visible to no user at all, while still being processed by a pipeline.
INSERT INTO public."UserVideoSources" ("Id","UserId","VideoSourceId")
SELECT md5('uvs-'||u||'-'||c)::uuid, md5('user-'||u)::uuid, md5('cam-'||c)::uuid
FROM generate_series(1,10) AS u,
     generate_series(1,40) AS c
WHERE u <> 6
  AND ( (u IN (1,2,3) AND c <= 34)         -- admins/operators: broad, but stale
        OR (u IN (4,5) AND c % 5 = u % 5)  -- viewers: a slice
        OR (u IN (7,8,9) AND c <= 12)
        OR (u = 10 AND c IN (1,2,3)) );

-- ---------------------------------------------------------------------
-- System configuration (subset of production keys that questions rely on)
-- ---------------------------------------------------------------------
INSERT INTO public."SystemConfig" ("Id","Key","Value") VALUES
    (md5('sc-defaultevent')::uuid,   'DefaultEvent',           'Face_Recognition'),
    (md5('sc-recconf')::uuid,        'RecognitionConfidence',  '0.5'),
    (md5('sc-playerip')::uuid,       'PlayerServerIp',         'webplayer'),
    (md5('sc-streamerip')::uuid,     'StreamerIp',             'streamer'),
    (md5('sc-snapip')::uuid,         'SnapshotServerIp',       ''),
    (md5('sc-servercfgport')::uuid,  'ServerConfigurationPort','5012'),
    (md5('sc-rabbitmq')::uuid,       'IsSendEventOnRabitMq',   'True'),
    (md5('sc-brokerip')::uuid,       'BrokerIp',               'localhost'),
    (md5('sc-brokerport')::uuid,     'BrokerPort',             '1883'),
    (md5('sc-rmqip')::uuid,          'RabbitMqIp',             'rabbitmq'),
    (md5('sc-rmqport')::uuid,        'RabbitMqPort',           '5672'),
    (md5('sc-retention')::uuid,      'EventRetentionDays',     '90'),
    (md5('sc-playercfgip')::uuid,    'PlayerServerConfigurationIp', NULL);

INSERT INTO public."EmailServer" ("Id","SMTPServer","SMTPPort","UserName","Password","IsValidated")
VALUES (md5('es-1')::uuid,'smtp.analytics.local',587,'alerts@analytics.local','enc:aa11',true),
       (md5('es-2')::uuid,'smtp.backup.local',   587,'alerts@backup.local',   'enc:bb22',false);

INSERT INTO public."SmsGateway" ("Id","Type","Discriminator","UserName","Password","Format","AccountSid","AuthToken","PhoneNumber")
VALUES (md5('sms-1')::uuid,'Twilio','TwilioGateway',NULL,NULL,NULL,'AC'||md5('sid'),'auth'||md5('tok'),'+911234567890'),
       (md5('sms-2')::uuid,'Http',  'HttpGateway','smsuser','smspass','GET|{to}|{msg}',NULL,NULL,NULL);

-- =====================================================================
-- EVENTS
-- =====================================================================
-- Bulk generation: 30 full days ending yesterday.
--   day 0  = 30 days ago
--   day 29 = yesterday
-- =====================================================================

INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('ev-'||c.i||'-'||d.d||'-'||g.g)::uuid,
    -- ---- _EventProperties -------------------------------------------
    CASE c.role
      WHEN 'FACE' THEN jsonb_build_object(
            'model','Person_60',
            'backend','nvidia_full0',
            'personName', pn.person,
            'personId', CASE WHEN pn.person = 'Unknown' THEN NULL
                             ELSE 'P-'||lpad(((c.i*7+g.g) % 250)::text,4,'0') END,
            'matched',   (pn.person <> 'Unknown'),
            'confidence', pn.conf,
            'roiName','ROI-'||(1+(g.g%2)))
      WHEN 'ANPR' THEN jsonb_build_object(
            'model','Model2',
            'backend','nvidia_full0',
            'plateNumber', (ARRAY['MH','KA','DL','TN','GJ','UP'])[1+((c.i+g.g)%6)]
                           ||lpad((10+((c.i*g.g)%89))::text,2,'0')
                           ||(ARRAY['AB','CD','EF','GH','JK'])[1+(g.g%5)]
                           ||lpad(((c.i*97+g.g*31)%9000+1000)::text,4,'0'),
            'vehicleType', (ARRAY['CAR','TRUCK','BIKE','BUS','LCV'])[1+(g.g%5)],
            'confidence', round((0.62 + ((c.i*13+g.g*7)%36)::numeric/100)::numeric,3),
            'speedKmph', 25+((c.i*g.g)%75))
      WHEN 'SAFETY' THEN jsonb_build_object(
            'model','Person_60','backend','nvidia_full0',
            'missingGear', (ARRAY['["helmet"]','["vest"]','["helmet","vest"]','["gloves"]'])[1+(g.g%4)]::jsonb,
            'confidence', round((0.55 + ((c.i*11+g.g*5)%40)::numeric/100)::numeric,3),
            'personCount', 1+(g.g%3))
      WHEN 'PERIM' THEN jsonb_build_object(
            'model','Model2','backend','nvidia_full0',
            'objectType',(ARRAY['person','vehicle','animal'])[1+(g.g%3)],
            'confidence', round((0.58 + ((c.i*17+g.g*3)%38)::numeric/100)::numeric,3),
            'roiName','ROI-'||(1+(g.g%3)),
            'direction',(ARRAY['IN','OUT'])[1+(g.g%2)])
      WHEN 'HW' THEN jsonb_build_object(
            'model','Model2','backend','nvidia_full0',
            'laneId',1+(g.g%4),
            'vehicleCount',5+((c.i*g.g)%60),
            'avgSpeedKmph',30+((c.i+g.g)%60),
            'confidence', round((0.70 + ((c.i*7+g.g*13)%25)::numeric/100)::numeric,3))
      WHEN 'FIRE' THEN jsonb_build_object(
            'model','Model2','backend','nvidia_full0',
            'severity',(ARRAY['LOW','MEDIUM','HIGH'])[1+(g.g%3)],
            'confidence', round((0.60 + ((c.i*19+g.g*11)%35)::numeric/100)::numeric,3))
      ELSE jsonb_build_object(
            'model','Model2','backend','nvidia_full0',
            'personCount',1+(g.g%8),
            'confidence', round((0.55 + ((c.i*23+g.g*29)%40)::numeric/100)::numeric,3))
    END,
    -- ---- EventName ---------------------------------------------------
    CASE c.role
      WHEN 'ANPR'   THEN (ARRAY['ANPR','ANPR','ANPR','ANPR','Speed_Detected','Wrong_Way_Detected','Illegal_Vehicle'])[1+(g.g%7)]
      WHEN 'FACE'   THEN 'Face_Recognition'
      WHEN 'PERIM'  THEN (ARRAY['Intrusion_Detected','Perimeter_Violation','Human_Detected','Human_Detected'])[1+(g.g%4)]
      WHEN 'SAFETY' THEN (ARRAY['Safety_Gear_Violation','Safety_Gear_Violation','Person_Fallen','Human_Pose_Detection'])[1+(g.g%4)]
      WHEN 'HW'     THEN (ARRAY['Highway_ATCC','Congestion_Detected','Traffic_Analyzer','Vehicle_Stopped'])[1+(g.g%4)]
      WHEN 'FIRE'   THEN (ARRAY['Smoke_Detected','Fire_Detected','Fog_Detected','Smoke_Detected'])[1+(g.g%4)]
      ELSE               (ARRAY['Motion_Detected','Human_Detected','Crowd_Detected','Motion_Detected'])[1+(g.g%4)]
    END,
    -- ---- Time (epoch ms) ---------------------------------------------
    ev.t_ms,
    -- ---- ReceivedTime  (A5 clock skew, A6 ingest lag) -----------------
    CASE
      WHEN c.i = 12 THEN ev.t_ms - (30000 + ((g.g*13)%45000))          -- A5: received BEFORE Time
      WHEN c.i = 21 THEN ev.t_ms + (45000 + ((g.g*17)%45000))          -- A6: 45-90 s lag
      ELSE               ev.t_ms + (180 + ((c.i*g.g*7919) % 1400))     -- normal 0.18-1.6 s
    END,
    md5('cam-'||c.i)::uuid,
    c.role||' event on '||c.name,
    -- ---- A18: a slice of events has no snapshot ----------------------
    CASE WHEN (c.i + g.g) % 23 = 0 THEN NULL
         ELSE '/snapshots/'||to_char(to_timestamp(ev.t_ms/1000),'YYYY/MM/DD')||'/'||md5('snap-'||c.i||'-'||d.d||'-'||g.g)||'.jpg' END,
    false,
    ((c.i*g.g) % 47 = 0),
    (c.role = 'ANPR' AND g.g % 11 = 0),
    c.mgr,
    md5('trk-'||c.i||'-'||d.d||'-'||g.g)::uuid
FROM (
    SELECT i,
           n.names[i] AS name,
           split_part(n.names[i],'-',1) AS role,
           CASE WHEN i <= 18 THEN md5('am-central')::uuid
                WHEN i <= 31 THEN md5('am-north')::uuid
                ELSE md5('am-south')::uuid END AS mgr,
           10 + ((i*13) % 41) AS base_rate
    FROM generate_series(1,40) AS i,
    LATERAL (SELECT ARRAY[
        'ANPR-Gate-01','ANPR-Gate-02','FACE-Entry-03','PERIM-East-04','SAFETY-Plant-05',
        'HW-Median-06','PERIM-North-07','ANPR-Toll-08','FIRE-Yard-09','FACE-Turnstile-10',
        'PERIM-West-11','LOBBY-Main-12','SAFETY-Weld-13','HW-Ramp-14','ANPR-Exit-15',
        'FIRE-Store-16','FACE-Gate-17','FACE-Lobby-18','PERIM-South-19','SAFETY-Crane-20',
        'HW-Median-21','ANPR-Gate-22','LOBBY-Rear-23','FIRE-Dock-24','PERIM-Fence-25',
        'FACE-Cafeteria-26','SAFETY-Loading-27','HW-Bridge-28','ANPR-Weighbridge-29','LOBBY-Side-30',
        'PERIM-Gate-31','FACE-Server-Room-32','SAFETY-Chem-33','HW-Tunnel-34','ANPR-Parking-35',
        'FIRE-Genset-36','PERIM-Roof-37','FACE-Reception-38','LOBBY-Atrium-39','SAFETY-Paint-40'
        ] AS names) n
) AS c
CROSS JOIN generate_series(0,29) AS d(d)
CROSS JOIN LATERAL (
    SELECT CASE
             WHEN c.i = 7  AND d.d >= 20 THEN 0                                  -- A3: silent
             WHEN c.i = 1  AND d.d  = 29 THEN GREATEST(1,(c.base_rate*30)/100)   -- A4: 30% yesterday
             ELSE c.base_rate
           END AS cnt
) AS r
CROSS JOIN LATERAL generate_series(1, r.cnt) AS g(g)
CROSS JOIN LATERAL (
    SELECT (extract(epoch FROM (date_trunc('day', now()) - interval '30 days'))::bigint
            + d.d*86400
            + ((g.g-1) * (86000 / GREATEST(r.cnt,1)))
            + ((c.i*g.g*31) % 40)) * 1000 AS t_ms
) AS ev
CROSS JOIN LATERAL (
    SELECT p.person,
           CASE WHEN c.i = 18                                    -- A8: chronically low confidence
                  THEN round((0.20 + ((c.i*g.g*7)%29)::numeric/100)::numeric,3)
                WHEN p.person = 'Unknown'
                  THEN round((0.21 + ((c.i*g.g*11)%28)::numeric/100)::numeric,3)
                ELSE round((0.55 + ((c.i*g.g*13)%44)::numeric/100)::numeric,3)
           END AS conf
    FROM (SELECT CASE
                   WHEN c.i = 18 AND g.g % 3 <> 0 THEN 'Unknown'  -- A8: mostly unmatched
                   ELSE (ARRAY['Rahul Sharma','Priya Nair','Amit Patel','Sneha Rao','Vikram Singh',
                               'Anita Desai','Karan Mehta','Divya Iyer','Unknown'])[1+((c.i*3+g.g*5)%9)]
                 END AS person) p
) AS pn
WHERE r.cnt > 0;

-- ---------------------------------------------------------------------
-- Partial "today" traffic (midnight -> now), at a reduced rate.
-- ANPR-Gate-01 stays depressed today as well, so A4 reads as an ongoing
-- incident rather than a one-day blip.
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('evtoday-'||c.i||'-'||g.g)::uuid,
    jsonb_build_object('model','Model2','backend','nvidia_full0',
                       'confidence', round((0.55 + ((c.i*g.g*17)%40)::numeric/100)::numeric,3)),
    CASE split_part(c.name,'-',1)
      WHEN 'ANPR'   THEN 'ANPR'
      WHEN 'FACE'   THEN 'Face_Recognition'
      WHEN 'PERIM'  THEN 'Intrusion_Detected'
      WHEN 'SAFETY' THEN 'Safety_Gear_Violation'
      WHEN 'HW'     THEN 'Highway_ATCC'
      WHEN 'FIRE'   THEN 'Smoke_Detected'
      ELSE 'Motion_Detected'
    END,
    t.t_ms,
    t.t_ms + (180 + ((c.i*g.g*7919) % 1400)),
    md5('cam-'||c.i)::uuid,
    'today traffic',
    '/snapshots/'||to_char(now(),'YYYY/MM/DD')||'/'||md5('snaptoday-'||c.i||'-'||g.g)||'.jpg',
    false, false, false,
    c.mgr,
    md5('trktoday-'||c.i||'-'||g.g)::uuid
FROM (
    SELECT i, n.names[i] AS name,
           CASE WHEN i <= 18 THEN md5('am-central')::uuid
                WHEN i <= 31 THEN md5('am-north')::uuid
                ELSE md5('am-south')::uuid END AS mgr,
           CASE WHEN i = 7 THEN 0
                WHEN i = 1 THEN 2
                ELSE GREATEST(1, (10 + ((i*13) % 41)) / 3) END AS cnt
    FROM generate_series(1,40) AS i,
    LATERAL (SELECT ARRAY[
        'ANPR-Gate-01','ANPR-Gate-02','FACE-Entry-03','PERIM-East-04','SAFETY-Plant-05',
        'HW-Median-06','PERIM-North-07','ANPR-Toll-08','FIRE-Yard-09','FACE-Turnstile-10',
        'PERIM-West-11','LOBBY-Main-12','SAFETY-Weld-13','HW-Ramp-14','ANPR-Exit-15',
        'FIRE-Store-16','FACE-Gate-17','FACE-Lobby-18','PERIM-South-19','SAFETY-Crane-20',
        'HW-Median-21','ANPR-Gate-22','LOBBY-Rear-23','FIRE-Dock-24','PERIM-Fence-25',
        'FACE-Cafeteria-26','SAFETY-Loading-27','HW-Bridge-28','ANPR-Weighbridge-29','LOBBY-Side-30',
        'PERIM-Gate-31','FACE-Server-Room-32','SAFETY-Chem-33','HW-Tunnel-34','ANPR-Parking-35',
        'FIRE-Genset-36','PERIM-Roof-37','FACE-Reception-38','LOBBY-Atrium-39','SAFETY-Paint-40'
        ] AS names) n
) AS c
CROSS JOIN LATERAL generate_series(1, c.cnt) AS g(g)
CROSS JOIN LATERAL (
    SELECT extract(epoch FROM date_trunc('day', now()))::bigint * 1000
           + ((g.g-1) * ((extract(epoch FROM now() - date_trunc('day', now()))::bigint * 1000)
                         / GREATEST(c.cnt,1))) AS t_ms
) AS t
WHERE c.cnt > 0;

-- ---------------------------------------------------------------------
-- A7  Duplicate TrackId burst on FACE-Entry-03, two days ago.
--     40 rows sharing 8 TrackIds, with identical "Time" inside each group.
--     This is what a retransmit / at-least-once delivery bug looks like.
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('dup-'||k||'-'||rep)::uuid,
    jsonb_build_object('model','Person_60','backend','nvidia_full0',
        'personName',(ARRAY['Rahul Sharma','Priya Nair','Amit Patel','Sneha Rao',
                            'Vikram Singh','Anita Desai','Karan Mehta','Divya Iyer'])[k],
        'personId','P-'||lpad((100+k)::text,4,'0'),
        'matched',true,
        'confidence',round((0.81 + (k::numeric/100))::numeric,3)),
    'Face_Recognition',
    base.t_ms,                                   -- identical Time within the group
    base.t_ms + 250 + rep*40,                    -- retransmits arrive slightly later
    md5('cam-3')::uuid,
    'FACE event on FACE-Entry-03',
    '/snapshots/dup/'||md5('dupsnap-'||k)||'.jpg',
    (rep > 1),                                   -- retransmits are flagged as updates
    false, false,
    md5('am-central')::uuid,
    md5('trk-dup-'||k)::uuid                     -- 8 distinct TrackIds, 5 rows each
FROM generate_series(1,8) AS k,
     generate_series(1,5) AS rep,
LATERAL (SELECT (extract(epoch FROM (date_trunc('day', now()) - interval '2 days'))::bigint
                 + 33600 + k*420) * 1000 AS t_ms) AS base;

-- ---------------------------------------------------------------------
-- A1  Orphan events: three cameras that were deleted from VideoSources
--     but whose events survive, because Events."VideoSourceId" has no FK.
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('orph-'||o.tag||'-'||g)::uuid,
    jsonb_build_object('model','Model2','backend','nvidia_full0',
                       'confidence', round((0.5 + (g%45)::numeric/100)::numeric,3)),
    o.ev,
    t.t_ms,
    t.t_ms + 300 + (g % 900),
    o.dead_id,
    'event from decommissioned camera '||o.tag,
    NULL,
    false, false, false,
    md5('am-central')::uuid,
    md5('trk-orph-'||o.tag||'-'||g)::uuid
FROM (VALUES
        (md5('cam-deleted-101')::uuid,'DEL-Gate-101','ANPR',              90),
        (md5('cam-deleted-102')::uuid,'DEL-Dock-102','Intrusion_Detected',75),
        (md5('cam-deleted-103')::uuid,'DEL-Hall-103','Face_Recognition',  55)
     ) AS o(dead_id, tag, ev, n)
CROSS JOIN LATERAL generate_series(1, o.n) AS g
CROSS JOIN LATERAL (
    SELECT (extract(epoch FROM (date_trunc('day', now()) - interval '30 days'))::bigint
            + (g % 26) * 86400 + (g * 913) % 86000) * 1000 AS t_ms
) AS t;

-- ---------------------------------------------------------------------
-- A2  Events with a NULL camera reference.  These are what make
--     "NOT IN (SELECT "Id" FROM "VideoSources")" silently return zero rows.
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('nullcam-'||g)::uuid,
    jsonb_build_object('model','Model2','source','manager-level'),
    (ARRAY['Pipeline_Started','Pipeline_Deleted','DEVICE_CONNECTED','DEVICE_DISCONNECTED'])[1+(g%4)],
    t.t_ms,
    t.t_ms + 200 + (g % 500),
    NULL,
    'manager-level event with no camera attribution',
    NULL,
    false, false, false,
    (ARRAY[md5('am-central')::uuid, md5('am-north')::uuid, md5('am-south')::uuid])[1+(g%3)],
    md5('trk-nullcam-'||g)::uuid
FROM generate_series(1,70) AS g
CROSS JOIN LATERAL (
    SELECT (extract(epoch FROM (date_trunc('day', now()) - interval '30 days'))::bigint
            + (g % 29) * 86400 + (g * 1471) % 86000) * 1000 AS t_ms
) AS t;

-- ---------------------------------------------------------------------
-- A10  A few future-dated events (bad camera clock pushed Time forward).
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('future-'||g)::uuid,
    jsonb_build_object('model','Model2','confidence',0.77),
    'Motion_Detected',
    (extract(epoch FROM now())::bigint + g * 3600) * 1000,
    extract(epoch FROM now())::bigint * 1000,
    md5('cam-30')::uuid,
    'future-dated event',
    NULL, false, false, false,
    md5('am-central')::uuid,
    md5('trk-future-'||g)::uuid
FROM generate_series(1,6) AS g;

-- ---------------------------------------------------------------------
-- A9  Force an EXACT tie in total event count between two cameras, so that
--     RANK / DENSE_RANK / ROW_NUMBER visibly disagree.
--     HW-Bridge-28 is topped up until it exactly matches PERIM-Fence-25,
--     which carries the higher base rate (48/day vs 46/day).
-- ---------------------------------------------------------------------
INSERT INTO public."Events"
    ("Id","_EventProperties","EventName","Time","ReceivedTime","VideoSourceId","Description",
     "SnapshotPath","Update","Starred","IsChallanRequested","AnalyticManagerId","TrackId")
SELECT
    md5('tie-'||g)::uuid,
    jsonb_build_object('model','Model2','backend','nvidia_full0','confidence',0.72,
                       'laneId',2,'vehicleCount',18,'avgSpeedKmph',54),
    'Highway_ATCC',
    t.t_ms,
    t.t_ms + 400,
    md5('cam-28')::uuid,
    'HW event on HW-Bridge-28',
    '/snapshots/tie/'||md5('tiesnap-'||g)||'.jpg',
    false, false, false,
    md5('am-north')::uuid,
    md5('trk-tie-'||g)::uuid
FROM generate_series(1, GREATEST(0,
        (SELECT count(*) FROM public."Events" WHERE "VideoSourceId" = md5('cam-25')::uuid)
      - (SELECT count(*) FROM public."Events" WHERE "VideoSourceId" = md5('cam-28')::uuid)
     )::int) AS g
CROSS JOIN LATERAL (
    SELECT (extract(epoch FROM (date_trunc('day', now()) - interval '15 days'))::bigint
            + (g * 271) % 86000) * 1000 AS t_ms
) AS t;

ANALYZE;

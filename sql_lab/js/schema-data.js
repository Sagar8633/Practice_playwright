/** Schema model used by the Schema viewer and the editor autocomplete. */

export const GAPS = [
  { id: 1, where: 'Events."VideoSourceId"', what: 'Indexed, but NO foreign key.', why: 'Delete a camera and its events survive, pointing at a UUID that no longer exists. Orphan events are permanent.' },
  { id: 2, where: 'VideoSources."activeConfigId"', what: 'NOT NULL, no default, NO foreign key.', why: 'A camera can name an active config that does not exist, or one belonging to a different camera.' },
  { id: 3, where: 'VideoSourceConfigs."ScheduleId"', what: 'NOT NULL, and there is no Schedules table at all.', why: 'Dangling by construction — every row points nowhere.' },
  { id: 4, where: 'AnalyticServers."AnalyticManagerId"', what: 'Indexed, but NO foreign key.', why: 'Servers outlive the manager that owned them.' },
  { id: 5, where: 'AspNetUsers."RoleId" vs AspNetUserRoles', what: 'Two independent sources of truth for a user\'s role.', why: 'The column and the junction table drift apart. Authorization then depends on which one the code reads.' },
  { id: 6, where: 'Events."TrackId"', what: 'DEFAULT gen_random_uuid().', why: 'If the producer forgets to set it, every event silently gets a fresh random track id — and track-based de-duplication stops working without any error.' },
];

export const TABLES = [
  { name: 'AnalyticManagers', group: 'control', pk: ['Id'], note: 'Deployment root. One per site.',
    cols: [['Id','uuid','PK'],['Name','text',''],['keyValuePairs','jsonb',''],['ManagerIp','text',''],['ManagerPort','integer','NOT NULL'],['RabbitMQIp','text',''],['RabbitMQPort','integer','NOT NULL'],['RabbitMqUserName','text',''],['RabbitMqUserPassword','text',''],['IsAnlayticManagerConnected','boolean','NOT NULL']] },

  { name: 'AnalyticServers', group: 'control', pk: ['Id'], note: 'Inference hosts. Self-referencing failover.',
    cols: [['Id','uuid','PK'],['Name','text','UNIQUE'],['Ip','text','UQ(Ip,RestPort)'],['RestPort','integer','NOT NULL'],['AlertListeningPort','integer','NOT NULL'],['AnalyticManagerId','uuid','⚠ no FK'],['Type','integer','NOT NULL'],['AlertListeningIp','text',''],['AlertListeningType','integer','NOT NULL'],['StreamingPort','integer',''],['FailoverServerId','uuid','FK → AnalyticServers'],['IsFailoverOnly','boolean','NOT NULL']] },

  { name: 'PipeLines', group: 'control', pk: ['Id'], note: 'Analytic pipeline on a server. MaxVideoSourceAllowed is enforced nowhere.',
    cols: [['Id','uuid','PK'],['Name','text','UNIQUE'],['Type','integer','NOT NULL'],['MaxVideoSourceAllowed','integer','NOT NULL'],['AnalyticServerId','uuid','FK → AnalyticServers'],['Enabled','boolean','NOT NULL']] },

  { name: 'PipeLineConfigs', group: 'control', pk: ['Id'], note: 'Key/value settings per pipeline.',
    cols: [['Id','uuid','PK'],['Key','text',''],['Value','text',''],['PipeLineId','uuid','FK → PipeLines'],['Type','integer','NOT NULL'],['ConfigType','integer','NOT NULL'],['BlockName','text','']] },

  { name: 'ExternalSources', group: 'device', pk: ['Id'], note: 'Upstream VMS / NVR. LastSynced shows staleness.',
    cols: [['Id','uuid','PK'],['Name','text','UNIQUE'],['Type','integer','NOT NULL'],['Ip','text',''],['Port','integer','NOT NULL'],['FailoverIp','text',''],['LastSynced','timestamp',''],['ServerState','integer','']] },

  { name: 'VideoSources', group: 'device', pk: ['Id'], note: 'Cameras. The centre of the schema.',
    cols: [['Id','uuid','PK'],['Name','text','UNIQUE'],['ProcessingWidth','integer','NOT NULL'],['ProcessingHeight','integer','NOT NULL'],['Ip','text',''],['AnalyticManagerId','uuid','FK → AnalyticManagers'],['configurationsAdded','boolean','NOT NULL'],['activeConfigId','uuid','⚠ NOT NULL, no FK'],['NormalizedId','serial',''],['Snapshot','text',''],['ExternalSourceType','integer',''],['ExternalVideoSourceId','text',''],['ExternalSourceId','uuid','FK → ExternalSources'],['UseStreamType','integer','']] },

  { name: 'VideoSourceConfigs', group: 'device', pk: ['Id'], note: 'Per-camera config. AppliedRules is a text[].',
    cols: [['Id','uuid','PK'],['ANPRParams','text',''],['BasicParams','text',''],['VideoSourceId','uuid','FK → VideoSources'],['DisabledRules','text',''],['AppliedRules','text[]',''],['ScheduleId','uuid','⚠ no such table']] },

  { name: 'VideoSourceStreamMappings', group: 'device', pk: ['Id'], note: 'RTSP URL per stream type. UNIQUE(VideoSourceId, StreamType).',
    cols: [['Id','uuid','PK'],['VideoSourceId','uuid','FK → VideoSources'],['StreamType','integer','NOT NULL'],['Url','text','NOT NULL']] },

  { name: 'PipeLineVideoSources', group: 'device', pk: ['Id'], note: 'N:M pipeline ↔ camera (intended assignment).',
    cols: [['Id','uuid','PK'],['PipeLineId','uuid','FK → PipeLines'],['VideoSourceId','uuid','FK → VideoSources']] },

  { name: 'AnalyticServerDeviceMapping', group: 'device', pk: ['Id'], note: 'Runtime placement (actual). Compare against PipeLineVideoSources.',
    cols: [['Id','uuid','PK'],['AnalyticServerId','uuid','FK → AnalyticServers'],['VideoSourceId','uuid','FK → VideoSources'],['PipelineId','uuid','FK → PipeLines'],['AnalyticManagerId','uuid','FK → AnalyticManagers'],['PipelineType','integer','']] },

  { name: 'Events', group: 'events', pk: ['Id'], note: 'The analytics payload. Time/ReceivedTime are epoch MILLISECONDS.',
    cols: [['Id','uuid','PK'],['_EventProperties','jsonb','confidence, personName, plateNumber…'],['EventName','text',''],['Time','bigint','NOT NULL, epoch ms'],['ReceivedTime','bigint','NOT NULL, epoch ms'],['VideoSourceId','uuid','⚠ no FK'],['Description','text',''],['SnapshotPath','text',''],['Update','boolean','NOT NULL, reserved word'],['Starred','boolean','NOT NULL'],['IsChallanRequested','boolean','NOT NULL'],['AnalyticManagerId','uuid','FK → AnalyticManagers'],['TrackId','uuid','⚠ defaulted']] },

  { name: 'AspNetRoles', group: 'identity', pk: ['Id'],
    cols: [['Id','uuid','PK'],['Name','varchar(256)',''],['NormalizedName','varchar(256)','UNIQUE'],['ConcurrencyStamp','text','']] },

  { name: 'AspNetRoleClaims', group: 'identity', pk: ['Id'], note: 'int PK from a sequence, not a uuid.',
    cols: [['Id','integer','PK (sequence)'],['RoleId','uuid','FK → AspNetRoles'],['ClaimType','text',''],['ClaimValue','text','']] },

  { name: 'AspNetUsers', group: 'identity', pk: ['Id'],
    cols: [['Id','uuid','PK'],['Preferences','text',''],['ProfileImagePath','text',''],['RoleId','uuid','⚠ FK, but see AspNetUserRoles'],['UserName','varchar(256)','UNIQUE'],['NormalizedUserName','varchar(256)','UNIQUE'],['Email','varchar(256)',''],['NormalizedEmail','varchar(256)',''],['EmailConfirmed','boolean','NOT NULL'],['PasswordHash','text',''],['SecurityStamp','text',''],['ConcurrencyStamp','text',''],['PhoneNumber','text',''],['PhoneNumberConfirmed','boolean','NOT NULL'],['TwoFactorEnabled','boolean','NOT NULL'],['LockoutEnd','timestamptz',''],['LockoutEnabled','boolean','NOT NULL'],['LoginWindow','boolean',''],['AccessFailedCount','integer','NOT NULL']] },

  { name: 'AspNetUserRoles', group: 'identity', pk: ['UserId','RoleId'], note: 'Composite PK. Second source of truth for roles.',
    cols: [['UserId','uuid','PK, FK → AspNetUsers'],['RoleId','uuid','PK, FK → AspNetRoles']] },

  { name: 'AspNetUserClaims', group: 'identity', pk: ['Id'],
    cols: [['Id','uuid','PK'],['UserId','uuid','FK → AspNetUsers'],['ClaimType','text',''],['ClaimValue','text','']] },

  { name: 'AspNetUserLogins', group: 'identity', pk: ['LoginProvider','ProviderKey'], note: 'Composite PK.',
    cols: [['LoginProvider','text','PK'],['ProviderKey','text','PK'],['ProviderDisplayName','text',''],['UserId','uuid','FK → AspNetUsers']] },

  { name: 'AspNetUserTokens', group: 'identity', pk: ['UserId','LoginProvider','Name'], note: 'Three-column composite PK.',
    cols: [['UserId','uuid','PK, FK → AspNetUsers'],['LoginProvider','text','PK'],['Name','text','PK'],['Value','text','']] },

  { name: 'UserVideoSources', group: 'identity', pk: ['Id'], note: 'Per-user camera access control.',
    cols: [['Id','uuid','PK'],['UserId','uuid','FK → AspNetUsers'],['VideoSourceId','uuid','FK → VideoSources']] },

  { name: 'SystemConfig', group: 'config', pk: ['Id'], note: "Key/value. Holds 'RecognitionConfidence' = 0.5.",
    cols: [['Id','uuid','PK'],['Key','text',''],['Value','text','']] },

  { name: 'EmailServer', group: 'config', pk: ['Id'],
    cols: [['Id','uuid','PK'],['SMTPServer','text','NOT NULL'],['SMTPPort','integer','NOT NULL'],['UserName','text','NOT NULL'],['Password','text','NOT NULL'],['IsValidated','boolean','NOT NULL']] },

  { name: 'SmsGateway', group: 'config', pk: ['Id'],
    cols: [['Id','uuid','PK'],['Type','text',''],['Discriminator','text','NOT NULL'],['UserName','text',''],['Password','text',''],['Format','text',''],['AccountSid','text',''],['AuthToken','text',''],['PhoneNumber','text','']] },
];

export const GROUPS = {
  control: { label: 'Control plane', color: '#7c8cff' },
  device: { label: 'Device / media', color: '#3fb98a' },
  events: { label: 'Events', color: '#e0913a' },
  identity: { label: 'Identity', color: '#c471d4' },
  config: { label: 'Configuration', color: '#8a93a8' },
};

/** Enum decoding that the questions rely on. */
export const ENUMS = {
  'AnalyticServers.Type': { 0: 'Standard', 1: 'Failover', 2: 'Edge' },
  'AnalyticServers.AlertListeningType': { 0: 'ZMQ', 1: 'HTTP' },
  'ExternalSources.ServerState': { 0: 'Healthy', 1: 'Degraded', 2: 'Unreachable' },
  'VideoSources.UseStreamType': { 0: 'Main', 1: 'Sub', 2: 'Tertiary' },
  'PipeLines.Type': { 0: 'General', 1: 'ANPR', 2: 'Face', 3: 'Perimeter', 4: 'Safety', 5: 'Highway', 6: 'Fire' },
};

export const AUTOCOMPLETE = (() => {
  const t = {};
  for (const tb of TABLES) t[`"${tb.name}"`] = tb.cols.map((c) => `"${c[0]}"`);
  return t;
})();

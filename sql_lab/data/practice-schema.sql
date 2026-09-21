-- =====================================================================
-- Analytics Manager - PRACTICE SCHEMA
-- =====================================================================
-- Faithful reproduction of the production Analytics Manager DDL.
--
-- DELIBERATE FIDELITY NOTES -- read before "fixing" anything:
--   * Identifiers keep their exact PascalCase quoting. Case-sensitive.
--   * The SIX unenforced relationships from production are preserved
--     ON PURPOSE. Events."VideoSourceId" has an index but NO foreign key,
--     exactly as in production. That is what makes orphan rows possible,
--     and orphan rows are the subject of many exercises here.
--   * uuid_generate_v4() -> gen_random_uuid() (built into PG13+, so the
--     uuid-ossp extension is not required). Behaviour is identical.
--   * The vector (pgvector) and postgis extensions are omitted: no table
--     in the supplied DDL declares a column of either type.
--   * Column "Update" is a reserved word and must always be quoted.
--
-- Runs on PGlite (PostgreSQL compiled to WebAssembly), entirely inside
-- the browser tab. There is no connection to any real database.
-- =====================================================================

-- ---------------------------------------------------------------------
-- CONTROL PLANE
-- ---------------------------------------------------------------------

CREATE TABLE public."AnalyticManagers" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" text NULL,
    "keyValuePairs" jsonb NULL,
    "ManagerIp" text NULL,
    "ManagerPort" integer NOT NULL,
    "RabbitMQIp" text NULL,
    "RabbitMQPort" integer NOT NULL,
    "RabbitMqUserName" text NULL,
    "RabbitMqUserPassword" text NULL,
    "IsAnlayticManagerConnected" boolean NOT NULL,
    CONSTRAINT "PK_AnalyticManagers" PRIMARY KEY ("Id")
);

CREATE TABLE public."AnalyticServers" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" text NULL,
    "Ip" text NULL,
    "RestPort" integer NOT NULL,
    "AlertListeningPort" integer NOT NULL,
    "AnalyticManagerId" uuid NULL,
    "Type" integer NOT NULL,
    "AlertListeningIp" text NULL,
    "AlertListeningType" integer NOT NULL DEFAULT 0,
    "StreamingPort" integer NULL,
    "FailoverServerId" uuid NULL,
    "IsFailoverOnly" boolean NOT NULL DEFAULT FALSE,
    CONSTRAINT "PK_AnalyticServers" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_AnalyticServer_Failover"
        FOREIGN KEY ("FailoverServerId") REFERENCES public."AnalyticServers"("Id")
);

CREATE UNIQUE INDEX "UQ_AnalyticServers_Ip_RestPort"
    ON public."AnalyticServers" ("Ip", "RestPort");

CREATE TABLE public."ExternalSources" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" text NULL,
    "Type" integer NOT NULL,
    "Ip" text NULL,
    "Port" integer NOT NULL,
    "FailoverIp" text NULL,
    "LastSynced" timestamp DEFAULT NOW(),
    "ServerState" integer DEFAULT 0,
    CONSTRAINT "PK_ExternalSources" PRIMARY KEY ("Id")
);

CREATE TABLE public."VideoSources" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" text NULL,
    "ProcessingWidth" integer NOT NULL,
    "ProcessingHeight" integer NOT NULL,
    "Ip" text NULL,
    "AnalyticManagerId" uuid NULL,
    "configurationsAdded" boolean NOT NULL DEFAULT false,
    "activeConfigId" uuid NOT NULL,
    "NormalizedId" SERIAL,
    "Snapshot" text NULL,
    "ExternalSourceType" integer NULL,
    "ExternalVideoSourceId" text NULL,
    "ExternalSourceId" uuid NULL,
    "UseStreamType" integer DEFAULT 0,
    CONSTRAINT "PK_VideoSources" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_VideoSources_AnalyticManagers_AnalyticManagerId"
        FOREIGN KEY ("AnalyticManagerId") REFERENCES public."AnalyticManagers" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_VideoSources_ExternalSources_ExternalSourceId"
        FOREIGN KEY ("ExternalSourceId") REFERENCES public."ExternalSources" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."PipeLines" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" text NULL,
    "Type" integer NOT NULL,
    "MaxVideoSourceAllowed" integer NOT NULL,
    "AnalyticServerId" uuid NOT NULL,
    "Enabled" boolean NOT NULL DEFAULT TRUE,
    CONSTRAINT "PK_PipeLines" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_PipeLines_AnalyticServers_AnalyticServerId"
        FOREIGN KEY ("AnalyticServerId") REFERENCES public."AnalyticServers" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."PipeLineConfigs" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Key" text NULL,
    "Value" text NULL,
    "PipeLineId" uuid NOT NULL,
    "Type" integer NOT NULL,
    "ConfigType" integer NOT NULL,
    "BlockName" text NULL,
    CONSTRAINT "PK_PipeLineConfigs" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_PipeLineConfigs_PipeLines_PipeLineId"
        FOREIGN KEY ("PipeLineId") REFERENCES public."PipeLines" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."VideoSourceConfigs" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "ANPRParams" text NULL,
    "BasicParams" text NULL,
    "VideoSourceId" uuid NOT NULL,
    "DisabledRules" text NULL,
    "AppliedRules" text[] NULL,
    "ScheduleId" uuid NOT NULL,
    CONSTRAINT "PK_VideoSourceConfigs" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_VideoSourceConfigs_VideoSources_VideoSourceId"
        FOREIGN KEY ("VideoSourceId") REFERENCES public."VideoSources" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."VideoSourceStreamMappings" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "VideoSourceId" uuid NOT NULL,
    "StreamType" integer NOT NULL,
    "Url" text NOT NULL,
    CONSTRAINT "PK_VideoSourceStreamMappings" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_VideoSourceStreamMappings_VideoSource"
        FOREIGN KEY ("VideoSourceId") REFERENCES public."VideoSources"("Id") ON DELETE CASCADE,
    CONSTRAINT "UQ_VideoSource_StreamType" UNIQUE ("VideoSourceId", "StreamType")
);

CREATE TABLE public."PipeLineVideoSources" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "PipeLineId" uuid NOT NULL,
    "VideoSourceId" uuid NOT NULL,
    CONSTRAINT "PK_PipeLineVideoSources" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_PipeLineVideoSources_PipeLines_PipeLineId"
        FOREIGN KEY ("PipeLineId") REFERENCES public."PipeLines" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_PipeLineVideoSources_VideoSources_VideoSourceId"
        FOREIGN KEY ("VideoSourceId") REFERENCES public."VideoSources" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AnalyticServerDeviceMapping" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "AnalyticServerId" uuid NOT NULL,
    "VideoSourceId" uuid NOT NULL,
    "PipelineId" uuid NULL,
    "AnalyticManagerId" uuid NULL,
    "PipelineType" integer NULL,
    CONSTRAINT "PK_AnalyticServerDeviceMapping" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_AnalyticServerDeviceMapping_AnalyticServers_AnalyticServerId"
        FOREIGN KEY ("AnalyticServerId") REFERENCES public."AnalyticServers" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_AnalyticServerDeviceMapping_Pipeline_PipelineId"
        FOREIGN KEY ("PipelineId") REFERENCES public."PipeLines" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_AnalyticServerDeviceMapping_VideoSources_VideoSourceId"
        FOREIGN KEY ("VideoSourceId") REFERENCES public."VideoSources" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_AnalyticServers_AnalyticManagers_AnalyticManagerId"
        FOREIGN KEY ("AnalyticManagerId") REFERENCES public."AnalyticManagers" ("Id") ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- EVENTS  (the analytics payload)
-- ---------------------------------------------------------------------

CREATE TABLE public."Events" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "_EventProperties" jsonb NULL,
    "EventName" text NULL,
    "Time" bigint NOT NULL,
    "ReceivedTime" bigint NOT NULL,
    "VideoSourceId" uuid NULL,
    "Description" text NULL,
    "SnapshotPath" text NULL,
    "Update" boolean NOT NULL,
    "Starred" boolean NOT NULL,
    "IsChallanRequested" boolean NOT NULL,
    "AnalyticManagerId" uuid NULL,
    "TrackId" uuid NOT NULL DEFAULT gen_random_uuid(),
    CONSTRAINT "PK_Events" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_Events_AnalyticManagers_AnalyticManagerId"
        FOREIGN KEY ("AnalyticManagerId") REFERENCES public."AnalyticManagers" ("Id") ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- IDENTITY  (ASP.NET Core Identity + custom extensions)
-- ---------------------------------------------------------------------

CREATE TABLE public."AspNetRoles" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Name" character varying(256) NULL,
    "NormalizedName" character varying(256) NULL,
    "ConcurrencyStamp" text NULL,
    CONSTRAINT "PK_AspNetRoles" PRIMARY KEY ("Id")
);

CREATE SEQUENCE public."AspNetRoleClaimSeq" START 33 INCREMENT BY 1 NO MINVALUE NO MAXVALUE NO CYCLE;

CREATE TABLE public."AspNetRoleClaims" (
    "Id" int NOT NULL DEFAULT nextval('public."AspNetRoleClaimSeq"'),
    "RoleId" uuid NOT NULL,
    "ClaimType" text NULL,
    "ClaimValue" text NULL,
    CONSTRAINT "PK_AspNetRoleClaims" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_AspNetRoleClaims_AspNetRoles_RoleId"
        FOREIGN KEY ("RoleId") REFERENCES public."AspNetRoles" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AspNetUsers" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Preferences" text NULL,
    "ProfileImagePath" text NULL,
    "RoleId" uuid NOT NULL,
    "UserName" character varying(256) NULL,
    "NormalizedUserName" character varying(256) NULL,
    "Email" character varying(256) NULL,
    "NormalizedEmail" character varying(256) NULL,
    "EmailConfirmed" boolean NOT NULL,
    "PasswordHash" text NULL,
    "SecurityStamp" text NULL,
    "ConcurrencyStamp" text NULL,
    "PhoneNumber" text NULL,
    "PhoneNumberConfirmed" boolean NOT NULL,
    "TwoFactorEnabled" boolean NOT NULL,
    "LockoutEnd" timestamp with time zone NULL,
    "LockoutEnabled" boolean NOT NULL,
    "LoginWindow" boolean DEFAULT true,
    "AccessFailedCount" integer NOT NULL,
    CONSTRAINT "PK_AspNetUsers" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_AspNetUsers_AspNetRoles_RoleId"
        FOREIGN KEY ("RoleId") REFERENCES public."AspNetRoles" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AspNetUserRoles" (
    "UserId" uuid NOT NULL,
    "RoleId" uuid NOT NULL,
    CONSTRAINT "PK_AspNetUserRoles" PRIMARY KEY ("UserId", "RoleId"),
    CONSTRAINT "FK_AspNetUserRoles_AspNetRoles_RoleId"
        FOREIGN KEY ("RoleId") REFERENCES public."AspNetRoles" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_AspNetUserRoles_AspNetUsers_UserId"
        FOREIGN KEY ("UserId") REFERENCES public."AspNetUsers" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AspNetUserClaims" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "UserId" uuid NOT NULL,
    "ClaimType" text NULL,
    "ClaimValue" text NULL,
    CONSTRAINT "PK_AspNetUserClaims" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_AspNetUserClaims_AspNetUsers_UserId"
        FOREIGN KEY ("UserId") REFERENCES public."AspNetUsers" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AspNetUserLogins" (
    "LoginProvider" text NOT NULL,
    "ProviderKey" text NOT NULL,
    "ProviderDisplayName" text NULL,
    "UserId" uuid NOT NULL,
    CONSTRAINT "PK_AspNetUserLogins" PRIMARY KEY ("LoginProvider", "ProviderKey"),
    CONSTRAINT "FK_AspNetUserLogins_AspNetUsers_UserId"
        FOREIGN KEY ("UserId") REFERENCES public."AspNetUsers" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."AspNetUserTokens" (
    "UserId" uuid NOT NULL,
    "LoginProvider" text NOT NULL,
    "Name" text NOT NULL,
    "Value" text NULL,
    CONSTRAINT "PK_AspNetUserTokens" PRIMARY KEY ("UserId", "LoginProvider", "Name"),
    CONSTRAINT "FK_AspNetUserTokens_AspNetUsers_UserId"
        FOREIGN KEY ("UserId") REFERENCES public."AspNetUsers" ("Id") ON DELETE CASCADE
);

CREATE TABLE public."UserVideoSources" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "UserId" uuid NOT NULL,
    "VideoSourceId" uuid NOT NULL,
    CONSTRAINT "PK_UserVideoSources" PRIMARY KEY ("Id"),
    CONSTRAINT "FK_UserVideoSources_AspNetUsers_UserId"
        FOREIGN KEY ("UserId") REFERENCES public."AspNetUsers" ("Id") ON DELETE CASCADE,
    CONSTRAINT "FK_UserVideoSources_VideoSources_VideoSourceId"
        FOREIGN KEY ("VideoSourceId") REFERENCES public."VideoSources" ("Id") ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- STANDALONE CONFIGURATION
-- ---------------------------------------------------------------------

CREATE TABLE public."SystemConfig" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Key" text NULL,
    "Value" text NULL,
    CONSTRAINT "PK_SystemConfig" PRIMARY KEY ("Id")
);

CREATE TABLE public."EmailServer" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "SMTPServer" text NOT NULL,
    "SMTPPort" integer NOT NULL,
    "UserName" text NOT NULL,
    "Password" text NOT NULL,
    "IsValidated" boolean NOT NULL DEFAULT false,
    CONSTRAINT "PK_EmailServer" PRIMARY KEY ("Id")
);

CREATE TABLE public."SmsGateway" (
    "Id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "Type" text NULL,
    "Discriminator" text NOT NULL,
    "UserName" text NULL,
    "Password" text NULL,
    "Format" text NULL,
    "AccountSid" text NULL,
    "AuthToken" text NULL,
    "PhoneNumber" text NULL,
    CONSTRAINT "PK_SmsGateway" PRIMARY KEY ("Id")
);

-- ---------------------------------------------------------------------
-- INDEXES  (exactly as production -- note which columns are indexed but
--           NOT constrained; that asymmetry is where the bugs live)
-- ---------------------------------------------------------------------

CREATE UNIQUE INDEX "IX_AnalyticServers_Name"        ON public."AnalyticServers" ("Name");
CREATE INDEX "IX_AnalyticServers_AnalyticManagerId"  ON public."AnalyticServers" ("AnalyticManagerId");
CREATE INDEX "IX_Events_AnalyticManagerId"           ON public."Events" ("AnalyticManagerId");
CREATE INDEX "IX_Events_VideoSourceId"               ON public."Events" ("VideoSourceId");
CREATE INDEX "IX_Events_Time"                        ON public."Events" ("Time");
CREATE INDEX "IX_VideoSources_AnalyticManagerId"     ON public."VideoSources" ("AnalyticManagerId");
CREATE UNIQUE INDEX "IX_VideoSources_Name"           ON public."VideoSources" ("Name");
CREATE UNIQUE INDEX "IX_ExternalSources_Name"        ON public."ExternalSources" ("Name");
CREATE INDEX "IX_PipeLineConfigs_PipeLineId"         ON public."PipeLineConfigs" ("PipeLineId");
CREATE INDEX "IX_PipeLines_AnalyticServerId"         ON public."PipeLines" ("AnalyticServerId");
CREATE UNIQUE INDEX "IX_PipeLines_Name"              ON public."PipeLines" ("Name");
CREATE INDEX "IX_PipeLineVideoSources_PipeLineId"    ON public."PipeLineVideoSources" ("PipeLineId");
CREATE INDEX "IX_PipeLineVideoSources_VideoSourceId" ON public."PipeLineVideoSources" ("VideoSourceId");
CREATE INDEX "IX_UserVideoSources_UserId"            ON public."UserVideoSources" ("UserId");
CREATE INDEX "IX_UserVideoSources_VideoSourceId"     ON public."UserVideoSources" ("VideoSourceId");
CREATE INDEX "IX_VideoSourceConfigs_VideoSourceId"   ON public."VideoSourceConfigs" ("VideoSourceId");
CREATE INDEX "IX_AspNetRoleClaims_RoleId"            ON public."AspNetRoleClaims" ("RoleId");
CREATE INDEX "IX_AspNetUserClaims_UserId"            ON public."AspNetUserClaims" ("UserId");
CREATE INDEX "IX_AspNetUserLogins_UserId"            ON public."AspNetUserLogins" ("UserId");
CREATE INDEX "IX_AspNetUserRoles_RoleId"             ON public."AspNetUserRoles" ("RoleId");
CREATE INDEX "IX_AspNetUsers_RoleId"                 ON public."AspNetUsers" ("RoleId");
CREATE UNIQUE INDEX "IX_AspNetUsers_UserName"        ON public."AspNetUsers" ("UserName");
CREATE UNIQUE INDEX "UserNameIndex"                  ON public."AspNetUsers" ("NormalizedUserName");
CREATE UNIQUE INDEX "RoleNameIndex"                  ON public."AspNetRoles" ("NormalizedName");
CREATE INDEX "EmailIndex"                            ON public."AspNetUsers" ("NormalizedEmail");

//+------------------------------------------------------------------+
//|                                                    ICE_Types.mqh |
//|  ICEburg - iceberg / absorption for XAUUSD                        |
//|  SECTION 1 equivalent: every enum and struct, in one place.       |
//|                                                                   |
//|  This is the MQL5 port of the Pine indicator of the same name.    |
//|  The two are kept deliberately explainable against each other:    |
//|  same section numbering, same identifier stems, same thresholds.  |
//|  Where MQL5 forced a different construction, the comment says so. |
//+------------------------------------------------------------------+
#property copyright "ICEburg"
#property strict

//--- ONE vocabulary for "why not". Values 0-29 are pre-signal GATE causes
//--- (owned by the filter chain, first-match-wins, most-upstream-first);
//--- 30+ are post-arm DEATH causes (owned by failure analysis). The panel,
//--- the histogram, the notification and the CSV all speak THIS enum.
enum ENUM_ICE_REASON
  {
   ICE_OK              = 0,   // OK
   ICE_WARMUP          = 1,   // WARMING UP
   ICE_OUTSIDE_SESS    = 2,   // OUTSIDE SESSION
   ICE_SESS_EDGE       = 3,   // SESSION EDGE TRIM
   ICE_LOW_ATR         = 4,   // DEAD TAPE (LOW ATR)
   ICE_NEWS_SPIKE      = 5,   // HIGH VOLATILITY / SPIKE
   ICE_CHOPPY          = 6,   // CHOPPY MARKET
   ICE_LOW_VOLUME      = 7,   // LOW VOLUME
   ICE_NO_LIQUIDITY    = 8,   // NO LIQUIDITY
   ICE_MID_RANGE       = 9,   // MIDDLE OF RANGE
   ICE_EXTENDED        = 10,  // EXTENDED MOVE
   ICE_VWAP_FAR        = 11,  // TOO FAR FROM VWAP
   ICE_NO_SWEEP        = 12,  // NO SWEEP
   ICE_NO_ABSORPTION   = 13,  // NO ABSORPTION
   ICE_ZONE_DEAD       = 14,  // ZONE INVALIDATED
   ICE_NO_REJECTION    = 15,  // NO REJECTION
   ICE_NO_DISPLACE     = 16,  // NO DISPLACEMENT
   ICE_NO_BOS          = 17,  // NO BOS
   ICE_NO_RETEST       = 18,  // NO RETEST
   ICE_LOW_SCORE       = 19,  // LOW CONFIDENCE
   ICE_POOR_RR         = 20,  // POOR RR
   ICE_WIDE_STOP       = 21,  // STOP TOO WIDE
   ICE_CONFLICT        = 22,  // DIRECTIONAL CONFLICT
   ICE_HTF_BLOCK       = 23,  // HTF BIAS OPPOSED
   ICE_COOLDOWN        = 24,  // COOLDOWN
   ICE_LOSS_COOLDOWN   = 25,  // LOSS COOLDOWN
   ICE_LOSS_STREAK     = 26,  // LOSS STREAK HALT
   ICE_DUPLICATE       = 27,  // DUPLICATE SIGNAL
   ICE_SLOTS_FULL      = 28,  // SETUP SLOTS FULL
   ICE_TRADE_OPEN      = 29,  // TRADE ALREADY OPEN
   ICE_OUT_OF_WINDOW   = 30,  // OUTSIDE BACKTEST WINDOW
   ICE_SPREAD_WIDE     = 31,  // SPREAD TOO WIDE
   //--- death causes
   ICE_D_TIMEOUT       = 40,  // EXPIRED (TIMEOUT)
   ICE_D_ZONE_BROKEN   = 41,  // ZONE BROKEN
   ICE_D_FALSE_SWEEP   = 42,  // FALSE SWEEP
   ICE_D_DISP_FAIL     = 43,  // DISPLACEMENT FAILED
   ICE_D_BOS_FAIL      = 44,  // BOS FAILED (FAKEOUT)
   ICE_D_RETEST_FAIL   = 45,  // RETEST FAILED
   ICE_D_EVICTED       = 46,  // EVICTED (SLOT REUSED)
   ICE_D_CONFLICT      = 47,  // KILLED BY CONFLICT
   ICE_D_SESSION_END   = 48,  // SESSION CLOSED
   ICE_D_STOPPED       = 49,  // STOPPED OUT
   ICE_D_TARGET        = 50,  // TARGET REACHED
   ICE_D_TIME_STOP     = 51   // TIME STOP
  };

//--- Setup lifecycle. RANK STRICTLY INCREASES and DEAD is ABSORBING - that
//--- pair of invariants is the entire non-repainting argument, and it is
//--- carried over from the Pine build unchanged.
enum ENUM_ICE_STATE
  {
   ICE_ST_IDLE      = 0,  // IDLE
   ICE_ST_ABSORBING = 1,  // ABSORBING
   ICE_ST_REJECTED  = 2,  // REJECTED
   ICE_ST_DISPLACED = 3,  // DISPLACED
   ICE_ST_BOS       = 4,  // BOS
   ICE_ST_RETEST    = 5,  // AWAITING RETEST
   ICE_ST_ARMED     = 6,  // ARMED
   ICE_ST_ACTIVE    = 7,  // ACTIVE
   ICE_ST_DEAD      = 8   // DEAD
  };

enum ENUM_ICE_ZONE
  {
   ICE_Z_PENDING = 0,  // PENDING
   ICE_Z_LIVE    = 1,  // LIVE
   ICE_Z_BROKEN  = 2,  // BROKEN
   ICE_Z_EXPIRED = 3   // EXPIRED
  };

enum ENUM_ICE_KIND
  {
   ICE_K_PDH = 0,  // PDH
   ICE_K_PDL = 1,  // PDL
   ICE_K_PWH = 2,  // PWH
   ICE_K_PWL = 3,  // PWL
   ICE_K_PSH = 4,  // PSH
   ICE_K_PSL = 5,  // PSL
   ICE_K_CSH = 6,  // CSH
   ICE_K_CSL = 7,  // CSL
   ICE_K_SWH = 8,  // SWING H
   ICE_K_SWL = 9,  // SWING L
   ICE_K_EQH = 10, // EQH
   ICE_K_EQL = 11, // EQL
   ICE_K_DOP = 12  // D-OPEN
  };

//--- Which estimator drives the delta PROXY. See the honesty note in ICE_Core.
enum ENUM_ICE_DELTA
  {
   ICE_DELTA_CLV   = 0,  // CLV x Volume (gap-aware) - Pine parity
   ICE_DELTA_WICK  = 1,  // Wick-weighted - Pine parity
   ICE_DELTA_TICK  = 2,  // Tick rule (volume-free) - Pine parity
   ICE_DELTA_REAL  = 3   // Real tick stream (MT5 only - BREAKS Pine parity)
  };

enum ENUM_ICE_SESSMODE
  {
   ICE_SESS_OFF     = 0,  // Off (24h)
   ICE_SESS_LDN_NY  = 1,  // London + NY
   ICE_SESS_OVERLAP = 2,  // Overlap only
   ICE_SESS_ALL     = 3   // All
  };

enum ENUM_ICE_HTFMODE
  {
   ICE_HTF_OFF     = 0,  // Off
   ICE_HTF_SOFT    = 1,  // Soft (score only)
   ICE_HTF_BLOCK   = 2,  // Block opposite
   ICE_HTF_REQUIRE = 3   // Require aligned
  };

enum ENUM_ICE_SLMODE
  {
   ICE_SL_STRUCT     = 0,  // Structure only
   ICE_SL_ATR        = 1,  // ATR only
   ICE_SL_STRUCT_ATR = 2   // Structure + ATR
  };

enum ENUM_ICE_ENTRY
  {
   ICE_ENTRY_RETEST  = 0,  // Retest (default - fewer, more selective)
   ICE_ENTRY_CONFIRM = 1   // Confirmation (enter on the BOS close)
  };

//+------------------------------------------------------------------+
//| STRUCTS                                                           |
//| `side` polarity is the ONE place that is not dir-polarity:        |
//|   side = +1  born from a HIGH -> acts as RESISTANCE               |
//|   side = -1  born from a LOW  -> acts as SUPPORT                  |
//| A LONG (dir=+1) needs SUPPORT, so eligibility is side == -dir.    |
//+------------------------------------------------------------------+
struct SIceLevel
  {
   double        price;
   ENUM_ICE_KIND kind;
   int           side;
   int           bornBar;      // bars-ago index is volatile; this is a bar COUNT id
   int           touches;
   int           lastTouch;
   double        strength;     // 0..1
   bool          active;
   bool          swept;
  };

struct SIceSwing
  {
   double price;
   int    bar;
   int    dir;                 // +1 = swing HIGH, -1 = swing LOW
   bool   broken;
  };

struct SIceSweep
  {
   int    dir;                 // +1 = SELL-side swept (bullish candidate)
   double lvlPrice;            // SNAPSHOT at candidate open
   double extreme;
   int    openBar;
   int    lvlIdx;
   double maxPen;
   double quality;             // 0..1
   bool   resolved;
  };

struct SIceZone
  {
   int            id;
   int            dir;
   double         top;
   double         bottom;
   int            bornBar;
   datetime       bornTime;
   double         atrRef;      // FROZEN at creation - the break buffer never rescales
   double         strength;    // 0..1
   int            tests;
   int            lastTest;
   double         invalid;
   ENUM_ICE_ZONE  state;
   double         swpExt;
   int            breakRun;
  };

struct SIceDisp
  {
   int    dir;
   double originLo;
   double originHi;
   double extreme;
   double fvgLo;
   double fvgHi;
   bool   hasFvg;
   double strength;
   int    bar;
  };

struct SIcePlan
  {
   int             dir;
   double          entry;
   double          stop;
   double          tp1;
   double          tp2;
   double          tp3;
   double          risk;       // NET risk per oz, cost included
   double          rr1;
   double          rr2;
   double          rr3;
   double          qRr;        // 0..1, feeds the score modifier
   bool            ok;
   ENUM_ICE_REASON why;
  };

struct SIceSetup
  {
   int             id;
   int             dir;
   ENUM_ICE_STATE  st;
   int             bornBar;
   int             stBar;
   int             zoneId;
   double          zoneTop;
   double          zoneBot;
   double          swpExt;
   double          bosLvl;
   double          dispOrg;
   double          dispFar;
   double          retestLv;
   double          score;
   SIcePlan        plan;
   ENUM_ICE_REASON death;
   //--- evidence snapshot frozen at the signal bar, for the panel/alert/CSV
   double          qLevel;
   double          qSweep;
   double          qRvol;
   double          qAbsorb;
   double          qReject;
   double          qDisp;
   double          qBos;
   double          qRetest;
  };

//--- The virtual tracker. MULTI-SLOT on purpose: a single slot silently
//--- discards every trade that outlives the cooldown and biases the loss
//--- streak toward fast-resolving trades only.
struct SIceVTrade
  {
   int             dir;
   int             openBar;
   double          entry;
   double          stop;
   double          be;
   double          tp1;
   double          tp2;
   double          tp3;
   double          risk;
   bool            tp1Hit;
   bool            tp2Hit;
   bool            isOpen;
   double          mfe;
   double          mae;
   double          rMult;
   int             closeBar;
   ENUM_ICE_REASON outcome;
  };

struct SIceStats
  {
   int    armed;
   int    signals;
   int    tp1;
   int    tp2;
   int    tp3;
   int    sl;
   int    be;
   int    wins;
   int    losses;
   double sumR;
   double grossW;
   double grossL;
  };

//+------------------------------------------------------------------+
//| Human text for the one vocabulary.                                |
//+------------------------------------------------------------------+
string IceReasonText(const ENUM_ICE_REASON r)
  {
   switch(r)
     {
      case ICE_OK:            return("OK");
      case ICE_WARMUP:        return("WARMING UP");
      case ICE_OUTSIDE_SESS:  return("OUTSIDE SESSION");
      case ICE_SESS_EDGE:     return("SESSION EDGE TRIM");
      case ICE_LOW_ATR:       return("DEAD TAPE (LOW ATR)");
      case ICE_NEWS_SPIKE:    return("HIGH VOLATILITY / SPIKE");
      case ICE_CHOPPY:        return("CHOPPY MARKET");
      case ICE_LOW_VOLUME:    return("LOW VOLUME");
      case ICE_NO_LIQUIDITY:  return("NO LIQUIDITY");
      case ICE_MID_RANGE:     return("MIDDLE OF RANGE");
      case ICE_EXTENDED:      return("EXTENDED MOVE");
      case ICE_VWAP_FAR:      return("TOO FAR FROM VWAP");
      case ICE_NO_SWEEP:      return("NO SWEEP");
      case ICE_NO_ABSORPTION: return("NO ABSORPTION");
      case ICE_ZONE_DEAD:     return("ZONE INVALIDATED");
      case ICE_NO_REJECTION:  return("NO REJECTION");
      case ICE_NO_DISPLACE:   return("NO DISPLACEMENT");
      case ICE_NO_BOS:        return("NO BOS");
      case ICE_NO_RETEST:     return("NO RETEST");
      case ICE_LOW_SCORE:     return("LOW CONFIDENCE");
      case ICE_POOR_RR:       return("POOR RR");
      case ICE_WIDE_STOP:     return("STOP TOO WIDE");
      case ICE_CONFLICT:      return("DIRECTIONAL CONFLICT");
      case ICE_HTF_BLOCK:     return("HTF BIAS OPPOSED");
      case ICE_COOLDOWN:      return("COOLDOWN");
      case ICE_LOSS_COOLDOWN: return("LOSS COOLDOWN");
      case ICE_LOSS_STREAK:   return("LOSS STREAK HALT");
      case ICE_DUPLICATE:     return("DUPLICATE SIGNAL");
      case ICE_SLOTS_FULL:    return("SETUP SLOTS FULL");
      case ICE_TRADE_OPEN:    return("TRADE ALREADY OPEN");
      case ICE_OUT_OF_WINDOW: return("OUTSIDE BACKTEST WINDOW");
      case ICE_SPREAD_WIDE:   return("SPREAD TOO WIDE");
      case ICE_D_TIMEOUT:     return("EXPIRED (TIMEOUT)");
      case ICE_D_ZONE_BROKEN: return("ZONE BROKEN");
      case ICE_D_FALSE_SWEEP: return("FALSE SWEEP");
      case ICE_D_DISP_FAIL:   return("DISPLACEMENT FAILED");
      case ICE_D_BOS_FAIL:    return("BOS FAILED (FAKEOUT)");
      case ICE_D_RETEST_FAIL: return("RETEST FAILED");
      case ICE_D_EVICTED:     return("EVICTED (SLOT REUSED)");
      case ICE_D_CONFLICT:    return("KILLED BY CONFLICT");
      case ICE_D_SESSION_END: return("SESSION CLOSED");
      case ICE_D_STOPPED:     return("STOPPED OUT");
      case ICE_D_TARGET:      return("TARGET REACHED");
      case ICE_D_TIME_STOP:   return("TIME STOP");
     }
   return("UNKNOWN");
  }

string IceStateText(const ENUM_ICE_STATE s)
  {
   switch(s)
     {
      case ICE_ST_IDLE:      return("IDLE");
      case ICE_ST_ABSORBING: return("ABSORBING");
      case ICE_ST_REJECTED:  return("REJECTED");
      case ICE_ST_DISPLACED: return("DISPLACED");
      case ICE_ST_BOS:       return("BOS");
      case ICE_ST_RETEST:    return("AWAITING RETEST");
      case ICE_ST_ARMED:     return("ARMED");
      case ICE_ST_ACTIVE:    return("ACTIVE");
      case ICE_ST_DEAD:      return("DEAD");
     }
   return("?");
  }

string IceDirName(const int dir) { return(dir > 0 ? "LONG" : (dir < 0 ? "SHORT" : "FLAT")); }
//+------------------------------------------------------------------+

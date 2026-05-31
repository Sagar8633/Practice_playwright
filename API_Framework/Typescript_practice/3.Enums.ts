// TypeScript Tutorial: Types, Type Annotation, आणि Type Inference (Marathi Version)
// ---------------------------------------------------------------------------
// ⚠️ सुधारणा: "Cannot redeclare block-scoped variable" त्रुटी टाळण्यासाठी
// सर्व उदाहरणे एका namespace मध्ये ठेवली आहेत.
// त्यामुळे variable names clash होणार नाहीत.

namespace TypeScriptExamples {

  // ---------------------------------------------------------------------------
  // 1️⃣ BASIC TYPES IN TYPESCRIPT
  // ---------------------------------------------------------------------------

  let age: number = 25; // number प्रकार
  let username: string = "Sagar"; // string प्रकार
  let isAdmin: boolean = true; // boolean प्रकार
  let skills: string[] = ["TS", "JS", "Playwright"]; // string array

  // ---------------------------------------------------------------------------
  // 2️⃣ TYPE ANNOTATION (आपण manually type देतो)
  // ---------------------------------------------------------------------------

  let mobile: number = 9876543210;
  let stockPrice: number;
  stockPrice = 2250;

  // ---------------------------------------------------------------------------
  // 3️⃣ TYPE INFERENCE (TypeScript स्वतः type ओळखतो)
  // ---------------------------------------------------------------------------

  let city = "Mumbai"; // inferred → string
  let count = 10; // inferred → number

  // ---------------------------------------------------------------------------
  // 4️⃣ TYPE ANNOTATION vs TYPE INFERENCE
  // ---------------------------------------------------------------------------

  let annotatedValue: number = 100; // annotation
  let autoValue = 100; // inference

  // ---------------------------------------------------------------------------
  // 5️⃣ FUNCTIONS
  // ---------------------------------------------------------------------------

  function addBad(a, b) {
    return a + b;
  }

  function add(a: number, b: number): number {
    return a + b;
  }

  function subtract(a: number, b: number) {
    return a - b; // inferred number
  }

  // ---------------------------------------------------------------------------
  // 6️⃣ OBJECT TYPE ANNOTATION
  // ---------------------------------------------------------------------------

  let user: {
    name: string;
    age: number;
    active: boolean;
  } = {
    name: "Sagar",
    age: 28,
    active: true,
  };

  // ---------------------------------------------------------------------------
  // 7️⃣ INTERVIEW POINTERS
  // ---------------------------------------------------------------------------

  // • Type Annotation → जेव्हा initial value माहित नसते
  // • Type Inference → TS स्वतः type ओळखतो
  // • Types → सुरक्षित code, compile-time errors, IntelliSense

} // namespace end

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 8️⃣ ENUMS IN TYPESCRIPT (Marathi Explanation + Realistic Examples)
// ---------------------------------------------------------------------------

// Enum म्हणजे related values चा समूह (set) readable नावांसह.
// हे code स्वच्छ, वाचायला सोपे आणि maintain करायला सोपे बनवते.

// ---------------------------------------------------------------------------
// 🟦 Numeric Enums (Default)
// ---------------------------------------------------------------------------

enum Direction {
  Up,     // 0
  Down,   // 1
  Left,   // 2
  Right   // 3
}

let move = Direction.Up;

// ---------------------------------------------------------------------------
// 🟩 String Enums (Most Useful)
// ---------------------------------------------------------------------------

enum Roles {
  Admin = "ADMIN",
  User = "USER",
  Guest = "GUEST"
}

let currentRole = Roles.Admin;

// ---------------------------------------------------------------------------
// 🔥 REALISTIC EXAMPLE 1: User Access Control System
// ---------------------------------------------------------------------------

enum PermissionLevel {
  Read = "READ",
  Write = "WRITE",
  Delete = "DELETE",
  Admin = "ADMIN_FULL_ACCESS"
}

function checkAccess(level: PermissionLevel) {
  if (level === PermissionLevel.Admin) {
    console.log("Full access granted");
  } else if (level === PermissionLevel.Delete) {
    console.log("Delete permissions granted");
  } else if (level === PermissionLevel.Write) {
    console.log("Write permissions granted");
  } else {
    console.log("Read-only access");
  }
}

// checkAccess(PermissionLevel.Delete);

// ---------------------------------------------------------------------------
// 🔥 REALISTIC EXAMPLE 2: Order Status Flow (E-commerce / ITMS)
// ---------------------------------------------------------------------------

enum OrderStatus {
  Placed = "PLACED",
  Packed = "PACKED",
  Shipped = "SHIPPED",
  Delivered = "DELIVERED",
  Cancelled = "CANCELLED"
}

function updateOrderStatus(status: OrderStatus) {
  console.log(`Order status updated to → ${status}`);
}

// updateOrderStatus(OrderStatus.Shipped);

// ---------------------------------------------------------------------------
// 🔥 REALISTIC EXAMPLE 3: Camera / Device Health Monitoring (Your Domain)
// ---------------------------------------------------------------------------

enum DeviceState {
  Online = "ONLINE",
  Offline = "OFFLINE",
  Faulty = "FAULTY",
  Maintenance = "MAINTENANCE"
}

function logDeviceState(deviceId: string, state: DeviceState) {
  console.log(`Device ${deviceId} is currently → ${state}`);
}

// logDeviceState("CAM1205", DeviceState.Faulty);

// ---------------------------------------------------------------------------
// 🔥 REALISTIC EXAMPLE 4: Violation Types (ANPR / VA Systems)
// ---------------------------------------------------------------------------

enum ViolationType {
  RedLight = "RED_LIGHT",
  NoHelmet = "NO_HELMET",
  Speeding = "OVERSPEED",
  TripleRiding = "TRIPLE_RIDING"
}

function createViolationEvent(type: ViolationType) {
  console.log(`Violation Event Triggered: ${type}`);
}

// createViolationEvent(ViolationType.Speeding);

// ---------------------------------------------------------------------------
// 🟧 Mixed Enums (शिफारस नाही)
// ---------------------------------------------------------------------------

enum Mixed {
  No = 0,
  Yes = "YES"
}

// ---------------------------------------------------------------------------
// 🟥 Reverse Mapping (फक्त Numeric Enums मध्ये)
// ---------------------------------------------------------------------------

enum Colors {
  Red, // 0
  Blue // 1
}

// Colors[0] → "Red"

// ---------------------------------------------------------------------------
// 🟫 Enum वापरून Function Example
// ---------------------------------------------------------------------------

enum Light {
  On,
  Off
}

function toggle(light: Light) {
  if (light === Light.On) {
    console.log("Light चालू आहे");
  } else {
    console.log("Light बंद आहे");
  }
}

// toggle(Light.On);

// ---------------------------------------------------------------------------
// 🟪 Const Enums (Performance optimized)
// ---------------------------------------------------------------------------

const enum Size {
  Small,
  Medium,
  Large
}

let selectedSize = Size.Small;

// ---------------------------------------------------------------------------
// 📝 Interview Notes (Enums)
// ---------------------------------------------------------------------------
// • Enum = group of named values
// • Numeric enums → auto numbering
// • String enums → readable, manual values
// • Reverse mapping → फक्त numeric enums मध्ये
// • const enum → performance साठी सर्वोत्तम

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 9️⃣ ADVANCED ENUM CONCEPTS (Complex Interview Topics)
// ---------------------------------------------------------------------------

// Interviewers mostly ask advanced scenarios like:
// • Enum vs Union Types
// • Enum Memory Impact
// • Enum as Types
// • Enum with Interfaces
// • Enum in Switch Cases
// • Enum for Bitwise Flags
// • Enum for State Machines

// ---------------------------------------------------------------------------
// 🔥 1. ENUM AS A TYPE (Very Important)
// ---------------------------------------------------------------------------

enum PaymentMode {
  Cash = "CASH",
  UPI = "UPI",
  Card = "CARD"
}

// Function expects ONLY enum values
function processPayment(mode: PaymentMode) {
  console.log(`Payment processed using: ${mode}`);
}

// processPayment(PaymentMode.UPI);

// This prevents invalid values → processPayment("PHONEPE") ❌

// ---------------------------------------------------------------------------
// 🔥 2. ENUM + INTERFACE (Complex Realistic Use Case)
// ---------------------------------------------------------------------------

interface Transaction {
  id: string;
  amount: number;
  mode: PaymentMode;
  status: OrderStatus;
}

let t1: Transaction = {
  id: "TXN9923",
  amount: 1200,
  mode: PaymentMode.Card,
  status: OrderStatus.Shipped,
};

// ---------------------------------------------------------------------------
// 🔥 3. ENUMS IN SWITCH CASES (Most Asked)
// ---------------------------------------------------------------------------

function handleOrderState(state: OrderStatus) {
  switch (state) {
    case OrderStatus.Placed:
      console.log("Order has been placed.");
      break;
    case OrderStatus.Shipped:
      console.log("Order shipped towards destination.");
      break;
    case OrderStatus.Delivered:
      console.log("Order delivered successfully.");
      break;
    default:
      console.log("Unknown state");
  }
}

// ---------------------------------------------------------------------------
// 🔥 4. ENUMS FOR BITWISE FLAGS (Advanced + Asked in Sr. QA/Automation)
// ---------------------------------------------------------------------------

// Example: Permissions that can be combined

enum FileAccess {
  Read = 1,        // 0001
  Write = 2,       // 0010
  Execute = 4,     // 0100
}

let userAccess = FileAccess.Read | FileAccess.Write; // 0001 | 0010 = 0011

// Check if user has Write Access
let hasWrite = (userAccess & FileAccess.Write) !== 0;
// console.log(hasWrite);

// ---------------------------------------------------------------------------
// 🔥 5. ENUMS FOR STATE MACHINES (High-level Interview Concept)
// ---------------------------------------------------------------------------

enum TrafficSignal {
  Red = "RED",
  Yellow = "YELLOW",
  Green = "GREEN",
}

function nextSignal(current: TrafficSignal): TrafficSignal {
  if (current === TrafficSignal.Red) return TrafficSignal.Green;
  if (current === TrafficSignal.Green) return TrafficSignal.Yellow;
  return TrafficSignal.Red;
}

// const next = nextSignal(TrafficSignal.Red);

// ---------------------------------------------------------------------------
// 🔥 6. ENUMS WITH MAPPED TYPES (Expert Level)
// ---------------------------------------------------------------------------

enum ApiMethods {
  Get = "GET",
  Post = "POST",
  Put = "PUT",
  Delete = "DELETE",
}

type ApiRouteMap = {
  [key in ApiMethods]: string;
};

const routes: ApiRouteMap = {
  GET: "/api/data",
  POST: "/api/create",
  PUT: "/api/update",
  DELETE: "/api/remove",
};

// ---------------------------------------------------------------------------
// END OF FILE – Marathi Version (with Advanced Interview Concepts)
// --------------------------------------------------------------------------- (with Realistic Enums)
// --------------------------------------------------------------------------- – Marathi Version (with Enums)
// --------------------------------------------------------------------------- – Marathi Version (Fixed Namespace Issue)
// ---------------------------------------------------------------------------

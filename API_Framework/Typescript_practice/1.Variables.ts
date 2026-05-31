/*  
==========================================================
 ⭐ TYPECRIPT VARIABLES — COMPLETE NOTES + INTERVIEW POINTS
==========================================================

🟦 In TypeScript, we use 3 keywords to declare variables:
1) var
2) let
3) const

⚠ Modern development में mostly "let" और "const" ही use होते हैं.
---------------------------------------------------------- 
*/

/*  
==========================================================
 1) var — पुराना तरीका (Avoid in modern TS)
==========================================================
- function scoped
- block scoped नहीं होता
- re-declaration allowed (bad practice)
- hoisting होता है → variable पहले undefined मिलता है
*/

var message: string = "Hello TS";
console.log(message);

// Example: Hoisting issue
// console.log(aVar); // Output: undefined (bad!)
var aVar = 10;


/*
==========================================================
 2) let — Modern + Safe (Recommended)
==========================================================
- Block scoped
- Re-declare ❌, Re-assign ✔
- TDZ (Temporal Dead Zone) → initialization से पहले access नहीं कर सकते
*/

let age: number = 25;
age = 26;

// Example: TDZ error
// console.log(xLet); // ❌ Cannot access 'xLet' before initialization
let xLet = 10;


/*
==========================================================
 3) const — Fixed Reference (Best for constants)
==========================================================
- Re-assign ❌
- Block scoped ✔
- BUT objects/arrays के अंदर values बदल सकते हैं
*/

const apiUrl: string = "https://api.example.com";

// Allowed (object mutation)
const user = { name: "Sagar" };
user.name = "Jadhav"; // ✔ allowed


/*
==========================================================
 TYPE ANNOTATION vs TYPE INFERENCE
==========================================================

1) Type Annotation = आप manually type लिखते हो
2) Type Inference = TS खुद type detect कर लेता है
*/

let count: number = 10;     // annotation
let city = "Mumbai";        // type inferred automatically


/*
==========================================================
 PRIMITIVE TYPES IN TS
==========================================================
string     → "hello"
number     → 120, 12.5
boolean    → true/false
any        → allow anything (avoid!)
unknown    → safer any
null       → empty
undefined  → not initialized
*/

let fullName: string = "Sagar";
let score: number = 85.5;
let isActive: boolean = true;
let something: any = "text";   // avoid!
let data: unknown = 10;        // better than any


/*
==========================================================
 REAL-WORLD VARIABLE EXAMPLES (API / PROJECTS)
==========================================================
*/

let userId: number = 101;
const token: string = "abxc67789";

let responseStatus: "success" | "error"; // union types


/*
==========================================================
 📌 INTERVIEW QUESTIONS (VERY IMPORTANT)
==========================================================

Q1) Difference between var, let, const?
----------------------------------------------------------
var  → function scope, re-declare allowed, hoisting issues  
let  → block scope, TDZ, safe  
const → block scope, cannot reassign, object mutation allowed  


Q2) What is Temporal Dead Zone (TDZ)?
----------------------------------------------------------
Variables declared with let/const cannot be accessed before initialization → error आएगा.


Q3) What is Type Inference?
----------------------------------------------------------
TypeScript automatically detects the variable type based on assigned value.


Q4) TypeScript statically typed है या dynamically typed?
----------------------------------------------------------
TypeScript → statically typed (compile time)  
JavaScript → dynamically typed (runtime)


Q5) any vs unknown ?
----------------------------------------------------------
any     → unsafe, type checking नहीं होता  
unknown → safer, use करने से पहले type check करना पड़ता है
*/


/*
==========================================================
 PRACTICE SECTION (Highly Recommended)
==========================================================
*/

// Practice 1: Declare variables of each type
let companyName: string = "I2V";
let employeeCount: number = 120;
let hiring: boolean = true;
let tempData: unknown;
let random: any;

// Practice 2: const with object mutation
const product = {
  id: 1,
  name: "Laptop",
  price: 45000
};

product.price = 50000; // ✔ allowed

// Practice 3: TDZ example
// console.log(testTDZ); // ❌ Error
let testTDZ = 20;

// Practice 4: Type inference
let language = "TypeScript"; // inferred as string

/*
==========================================================
 END OF NOTES ✔  
==========================================================
*/

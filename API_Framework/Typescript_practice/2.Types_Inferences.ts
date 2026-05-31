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
// END OF FILE – Marathi Version (Fixed Namespace Issue)
// ---------------------------------------------------------------------------
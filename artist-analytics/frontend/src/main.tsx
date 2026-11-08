/**
 * main.tsx — where the app starts.
 *
 * NEW TO REACT? This file is the three-line bridge between plain HTML and
 * React: find the empty <div> in index.html, and tell React to draw <App />
 * inside it. Everything else in src/ hangs off that one component.
 */

// React itself. Needed here for <React.StrictMode> below.
import React from "react";
// The browser-specific half of React. `react-dom/client` gives us createRoot,
// which connects React to a real DOM element on the page.
import ReactDOM from "react-dom/client";
// Our top-level component — the root of the component tree.
import App from "./App";
// Importing CSS from JavaScript looks odd, but Vite understands it: the
// stylesheet is bundled and injected into the page. Because it is imported
// here, at the root, its rules are global to the whole app.
import "./styles.css";

// document.getElementById returns the <div id="root"> from index.html.
// The trailing `!` is TypeScript only: "trust me, this element exists".
// (If you renamed the div's id, this is the line that would break.)
const rootElement = document.getElementById("root")!;

// createRoot hands that div over to React; .render() draws into it.
ReactDOM.createRoot(rootElement).render(
  // StrictMode is a development-only wrapper. It renders components twice to
  // surface bugs caused by impure code or missing effect cleanup. It adds no
  // markup and disappears in a production build.
  <React.StrictMode>
    {/* Angle brackets around a name = "render this component here".
        <App /> calls the App() function in App.tsx. */}
    <App />
  </React.StrictMode>,
);

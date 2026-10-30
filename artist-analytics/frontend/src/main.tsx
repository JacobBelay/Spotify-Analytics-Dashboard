import React from "react"; // Imports React Library Into This File
import ReactDOM from "react-dom/client"; // Connects React's Components To The Browser's DOM (By Providing createRoot)
import App from "./App"; // Imports the root component that holds the whole app
import "./styles.css"; // Connects Css (Global styles for the whole app)

ReactDOM.createRoot(document.getElementById("root")! ).render( // Finds the empty div in index.html
  <React.StrictMode> 
    <App />  {/* // calls the app function in App.tsx */}
   
    
  </React.StrictMode>, // For Safer development
 
);

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  // O app não tem tema escuro (Card, layout e Badge são só claros). Com o padrão
  // "media", as classes dark: ligavam pelo tema do SO e deixavam texto branco em
  // card branco. Com "class", elas só valem se alguém adicionar a classe "dark".
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
        },
      },
    },
  },
  plugins: [],
};

export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <p className="footer-disclaimer">
          Results are probability estimates from automated signals, not a
          determination of fact. Built as a university project — not intended
          for high-stakes decisions.
        </p>
        <p className="footer-copyright">
          © {year} Is it AI? · Built with FastAPI and React.
        </p>
      </div>
    </footer>
  );
}

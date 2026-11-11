import { usePrefs } from "../prefs";
import { T } from "../strings";
import Logo from "./Logo";
import { IconMoon, IconSun } from "./Icons";

export default function Topbar() {
  const { showEnglish, setShowEnglish, theme, setTheme } = usePrefs();
  return (
    <div className="topbar">
      <a className="topbar-brand" href="#top" aria-label="Huqooq-e-Zan">
        <Logo size={40} />
        <span className="topbar-name"><span lang="ur" className="topbar-ur">حقوقِ زن</span><span className="topbar-en" lang="en" dir="ltr">Huqooq-e-Zan</span></span>
      </a>
      <div className="topbar-actions">
        <button type="button" className="tb-btn" aria-pressed={showEnglish} onClick={() => setShowEnglish(!showEnglish)}>{T.englishToggle}</button>
        <button type="button" className="tb-btn tb-icon" aria-label={theme === "dark" ? T.themeLight : T.themeDark} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <IconSun /> : <IconMoon />}
        </button>
      </div>
    </div>
  );
}

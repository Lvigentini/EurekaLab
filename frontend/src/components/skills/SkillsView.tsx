import { useState } from 'react';
import { SkillHubPanel } from './SkillHubPanel';
import { SkillLibrary } from './SkillLibrary';
import { SelectedSkillsPanel } from './SelectedSkillsPanel';
import { useSkillStore } from '@/store/skillStore';

export function SkillsView() {
  const [hubStatus, setClawStatus] = useState('');
  const [hubStatusError, setClawStatusError] = useState(false);
  const availableSkills = useSkillStore((s) => s.availableSkills);
  const selectedSkills = useSkillStore((s) => s.selectedSkills);

  const handleStatus = (msg: string, isError = false) => {
    setClawStatus(msg);
    setClawStatusError(isError);
  };

  const seedCount = availableSkills.filter((s) => s.source === 'seed').length;
  const learnedCount = availableSkills.filter((s) => s.source === 'distilled').length;

  return (
    <div className="skills-page">
      {/* Hero banner */}
      <div className="skills-hero">
        <div className="skills-hero-text">
          <h2 className="skills-hero-title">Proof Strategies &amp; Skills</h2>
          <p className="skills-hero-sub">
            Skills guide how EurekaLab approaches each research task — from choosing proof techniques
            to structuring analytical decompositions. The system learns new strategies after every successful session.
          </p>
        </div>
        <div className="skills-hero-stats">
          <div className="skills-hero-stat">
            <span className="skills-hero-stat-num">{availableSkills.length}</span>
            <span className="skills-hero-stat-label">Available</span>
          </div>
          <div className="skills-hero-stat">
            <span className="skills-hero-stat-num">{selectedSkills.length}</span>
            <span className="skills-hero-stat-label">Active</span>
          </div>
          <div className="skills-hero-stat">
            <span className="skills-hero-stat-num">{seedCount}</span>
            <span className="skills-hero-stat-label">Built-in</span>
          </div>
          {learnedCount > 0 && (
            <div className="skills-hero-stat">
              <span className="skills-hero-stat-num">{learnedCount}</span>
              <span className="skills-hero-stat-label">Learned</span>
            </div>
          )}
        </div>
      </div>

      {/* Add Skills bar */}
      <SkillHubPanel status={hubStatus} statusError={hubStatusError} onStatus={handleStatus} />

      {/* Selected skills */}
      <SelectedSkillsPanel />

      {/* Skill Library */}
      <SkillLibrary onSkillHubStatus={handleStatus} />
    </div>
  );
}

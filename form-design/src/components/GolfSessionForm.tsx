import React, { useEffect, useMemo, useState } from 'react';
import './GolfSessionForm.css';

type FormContext = {
  session_id: string;
  player_id: string;
  lead_name: string;
  target_date: string;
  candidate_courses: string[];
  shared_courses?: string[];
  is_new_player: boolean;
  agent_phone: string;
};

type FormResponse = {
  token: string;
  is_attending: boolean;
  approved_courses: string[];
  available_time_blocks: string[];
  player_profile?: {
    name?: string;
    general_availability: string[];
    course_preferences: string[];
    standing_constraints?: string;
  };
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';

const timeSlots = [
  { id: 'early_morning', label: 'Early Morning (8-10 AM)' },
  { id: 'late_morning', label: 'Late Morning (10 AM-12 PM)' },
  { id: 'early_afternoon', label: 'Early Afternoon (12-2 PM)' },
];

function GolfSessionForm() {
  const [context, setContext] = useState<FormContext | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [isAttending, setIsAttending] = useState<boolean | null>(null);
  const [selectedCourses, setSelectedCourses] = useState<string[]>([]);
  const [customCourse, setCustomCourse] = useState('');
  const [selectedTimeSlots, setSelectedTimeSlots] = useState<string[]>([]);
  const [playerName, setPlayerName] = useState('');
  const [generalAvailability, setGeneralAvailability] = useState<string[]>([]);
  const [coursePreferences, setCoursePreferences] = useState('');
  const [standingConstraints, setStandingConstraints] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const token = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('token') || '';
  }, []);

  useEffect(() => {
    async function fetchContext() {
      if (!token) {
        setLoadError('Missing form token in URL.');
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/form-context?token=${encodeURIComponent(token)}`);
        if (!response.ok) {
          throw new Error('Could not load session form context.');
        }
        const data = (await response.json()) as FormContext;
        setContext(data);
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : 'Unable to load form.');
      } finally {
        setIsLoading(false);
      }
    }

    void fetchContext();
  }, [token]);

  const handleCourseToggle = (course: string) => {
    setSelectedCourses(prev =>
      prev.includes(course) ? prev.filter(c => c !== course) : [...prev, course]
    );
  };

  const handleAddCustomCourse = () => {
    const normalized = customCourse.trim();
    if (!normalized) return;
    if (!selectedCourses.includes(normalized)) {
      setSelectedCourses(prev => [...prev, normalized]);
    }
    setCustomCourse('');
  };

  const handleTimeSlotToggle = (slotId: string) => {
    setSelectedTimeSlots(prev =>
      prev.includes(slotId) ? prev.filter(s => s !== slotId) : [...prev, slotId]
    );
  };

  const handleAvailabilityToggle = (slotId: string) => {
    setGeneralAvailability(prev =>
      prev.includes(slotId) ? prev.filter(s => s !== slotId) : [...prev, slotId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!context || !token) {
      setSubmitError('Missing form context. Please reopen the link from your text message.');
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);

    const payload: FormResponse = {
      token,
      is_attending: Boolean(isAttending),
      approved_courses: isAttending ? selectedCourses : [],
      available_time_blocks: isAttending ? selectedTimeSlots : [],
    };

    if (context.is_new_player && isAttending) {
      payload.player_profile = {
        name: playerName.trim() || undefined,
        general_availability: generalAvailability,
        course_preferences: coursePreferences
          .split(',')
          .map(course => course.trim())
          .filter(Boolean),
        standing_constraints: standingConstraints.trim() || undefined,
      };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/form-response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(errorData.detail || 'Submission failed.');
      }

      setIsSubmitted(true);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = () => {
    if (isAttending === null) return false;
    if (isAttending && (selectedCourses.length === 0 || selectedTimeSlots.length === 0)) return false;
    if (context?.is_new_player && isAttending && !playerName.trim()) return false;
    return true;
  };

  if (isLoading) {
    return (
      <div className="golf-form-container">
        <div className="golf-form-card">
          <p>Loading your invite...</p>
        </div>
      </div>
    );
  }

  if (loadError || !context) {
    return (
      <div className="golf-form-container">
        <div className="golf-form-card">
          <h2>Link issue</h2>
          <p>{loadError || 'Could not load your invite.'}</p>
        </div>
      </div>
    );
  }

  const leadName = context.lead_name;
  const targetDate = new Date(context.target_date).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
  const candidateCourses = context.candidate_courses;
  const sharedCourses = context.shared_courses ?? [];
  const displayCourses = Array.from(new Set([...candidateCourses, ...sharedCourses]));
  const isNewPlayer = context.is_new_player;
  const agentPhone = context.agent_phone;

  if (isSubmitted) {
    return (
      <div className="golf-form-container">
        <div className="golf-form-card">
          <div className="success-state">
            <div className="success-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h2>You're all set!</h2>
            <p>
              {isAttending
                ? `${leadName} will get back to you once everyone responds.`
                : `We've let ${leadName} know you can't make it this time.`}
            </p>
            <div className="contact-info">
              <p>Need to make changes? Text the agent at:</p>
              <span className="phone-number">{agentPhone}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="golf-form-container">
      <div className="golf-form-card">
        <div className="form-header">
          <div className="golf-icon">⛳</div>
          <h1>Golf Round</h1>
          <p className="subtitle">
            <span className="lead-name">{leadName}</span> is organizing a round for <span className="target-date">{targetDate}</span>
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-section">
            <h3>Are you in?</h3>
            <div className="attendance-buttons">
              <button
                type="button"
                className={`attendance-btn ${isAttending === true ? 'selected yes' : ''}`}
                onClick={() => setIsAttending(true)}
              >
                <span className="btn-icon">✓</span>
                <span>Yes, I'm in!</span>
              </button>
              <button
                type="button"
                className={`attendance-btn ${isAttending === false ? 'selected no' : ''}`}
                onClick={() => setIsAttending(false)}
              >
                <span className="btn-icon">✕</span>
                <span>Can't make it</span>
              </button>
            </div>
          </div>

          {isAttending && (
            <>
              <div className="form-section">
                <h3>Which courses work for you?</h3>
                <p className="section-hint">Select all that you'd be happy playing</p>
                <div className="checkbox-group courses">
                  {displayCourses.map(course => (
                    <label key={course} className={`checkbox-card ${selectedCourses.includes(course) ? 'checked' : ''}`}>
                      <input
                        type="checkbox"
                        checked={selectedCourses.includes(course)}
                        onChange={() => handleCourseToggle(course)}
                      />
                      <span className="checkbox-indicator">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </span>
                      <span className="checkbox-label">{course}</span>
                    </label>
                  ))}
                </div>
                <div className="form-field" style={{ marginTop: '12px' }}>
                  <label htmlFor="customCourse">Add another course</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="text"
                      id="customCourse"
                      value={customCourse}
                      onChange={e => setCustomCourse(e.target.value)}
                      placeholder="Enter a course name"
                    />
                    <button type="button" onClick={handleAddCustomCourse}>
                      Add
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>What tee times work for you?</h3>
                <p className="section-hint">Select all available time windows</p>
                <div className="checkbox-group time-slots-grid">
                  {timeSlots.map(slot => (
                    <label key={slot.id} className={`checkbox-card time-card-compact ${selectedTimeSlots.includes(slot.id) ? 'checked' : ''}`}>
                      <input
                        type="checkbox"
                        checked={selectedTimeSlots.includes(slot.id)}
                        onChange={() => handleTimeSlotToggle(slot.id)}
                      />
                      <span className="checkbox-indicator">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </span>
                      <span className="time-slot-label">{slot.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {isNewPlayer && (
                <div className="form-section profile-section">
                  <div className="profile-header">
                    <h3>Quick profile setup</h3>
                    <span className="new-badge">First time</span>
                  </div>
                  <p className="section-hint">This helps coordinate future rounds faster</p>

                  <div className="form-field">
                    <label htmlFor="playerName">Your name</label>
                    <input
                      type="text"
                      id="playerName"
                      value={playerName}
                      onChange={e => setPlayerName(e.target.value)}
                      placeholder="What should we call you?"
                      required
                    />
                  </div>

                  <div className="form-field">
                    <label>General availability</label>
                    <p className="field-hint">When can you typically play golf?</p>
                    <div className="checkbox-group horizontal">
                      {timeSlots.map(slot => (
                        <label key={`general-${slot.id}`} className={`checkbox-pill ${generalAvailability.includes(slot.id) ? 'checked' : ''}`}>
                          <input
                            type="checkbox"
                            checked={generalAvailability.includes(slot.id)}
                            onChange={() => handleAvailabilityToggle(slot.id)}
                          />
                          <span>{slot.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="form-field">
                    <label htmlFor="coursePrefs">Favorite courses</label>
                    <input
                      type="text"
                      id="coursePrefs"
                      value={coursePreferences}
                      onChange={e => setCoursePreferences(e.target.value)}
                      placeholder="e.g., Bethpage, Pelham Bay, Van Cortlandt"
                    />
                    <span className="field-hint">Comma-separated list of courses you enjoy</span>
                  </div>

                  <div className="form-field">
                    <label htmlFor="standingConstraints">Any standing constraints?</label>
                    <input
                      type="text"
                      id="standingConstraints"
                      value={standingConstraints}
                      onChange={e => setStandingConstraints(e.target.value)}
                      placeholder="e.g., No Sundays"
                    />
                  </div>
                </div>
              )}
            </>
          )}

          <div className="form-actions">
            <button
              type="submit"
              className="submit-btn"
              disabled={!isFormValid() || isSubmitting}
            >
              {isSubmitting ? (
                <span className="loading-state">
                  <span className="spinner"></span>
                  Submitting...
                </span>
              ) : (
                isAttending === false ? 'Let them know' : 'Submit my preferences'
              )}
            </button>
          </div>

          {submitError && (
            <div className="form-footer">
              <p>{submitError}</p>
            </div>
          )}
        </form>

        <div className="form-footer">
          <p>
            Powered by <strong>Golf Agent</strong> 🤖
          </p>
        </div>
      </div>
    </div>
  );
}

export default GolfSessionForm;

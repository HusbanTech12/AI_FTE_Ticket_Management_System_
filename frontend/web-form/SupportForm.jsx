/**
 * SupportForm - Customer-facing web support form
 *
 * A complete, production-ready React component for collecting
 * customer support requests with professional animations and UX.
 *
 * Features:
 * - Smooth page-level transitions with fade-in
 * - Staggered form field animations on load
 * - Micro-interactions (hover, focus, active states)
 * - Loading spinner with pulse animation
 * - Success state with confetti effect
 * - Error shake animation
 * - Form field character count with smooth progress
 * - Responsive design with accessibility
 *
 * @author TechCorp SaaS - Enhanced with animations
 * @license MIT
 */

import React, { useState, useEffect } from 'react';

// ----------------------------------------------------------------------------
// Constants and Types
// ----------------------------------------------------------------------------

const CATEGORIES = [
  { value: 'general', label: 'General Question', icon: '💬' },
  { value: 'technical', label: 'Technical Support', icon: '🔧' },
  { value: 'billing', label: 'Billing Inquiry', icon: '💳' },
  { value: 'bug_report', label: 'Bug Report', icon: '🐛' },
  { value: 'feedback', label: 'Feedback / Feature Request', icon: '💡' }
];

const PRIORITIES = [
  { value: 'low', label: 'Low - Not urgent', color: 'text-gray-500' },
  { value: 'medium', label: 'Medium - Need help soon', color: 'text-yellow-600' },
  { value: 'high', label: 'High - Urgent issue', color: 'text-red-600' }
];

const MAX_MESSAGE_LENGTH = 3000;

// Animation variants
const ANIMATIONS = {
  fadeIn: 'animate-fade-in',
  slideUp: 'animate-slide-up',
  slideIn: 'animate-slide-in',
  scaleIn: 'animate-scale-in',
  pulse: 'animate-pulse-slow',
  shake: 'animate-shake'
};

// ----------------------------------------------------------------------------
// Helper Components
// ----------------------------------------------------------------------------

/**
 * Confetti particle component for success state
 */
const Confetti = () => {
  const particles = Array.from({ length: 50 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    animationDelay: `${Math.random() * 2}s`,
    animationDuration: `${2 + Math.random() * 2}s`,
    color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][Math.floor(Math.random() * 5)]
  }));

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
      {particles.map(p => (
        <div
          key={p.id}
          className="absolute w-2 h-2 rounded-full animate-confetti"
          style={{
            left: p.left,
            top: '-10px',
            backgroundColor: p.color,
            animationDelay: p.animationDelay,
            animationDuration: p.animationDuration
          }}
        />
      ))}
    </div>
  );
};

/**
 * Animated input field wrapper with label
 */
const AnimatedInput = ({
  label,
  id,
  name,
  type = 'text',
  value,
  onChange,
  required = false,
  disabled = false,
  placeholder,
  helpText,
  minLength,
  maxLength,
  className = '',
  rows,
  isTextarea = false,
  error
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const hasValue = value && value.length > 0;

  const inputClasses = `
    w-full px-4 py-2.5 border rounded-lg
    bg-white
    transition-all duration-200 ease-out
    disabled:bg-gray-100 disabled:cursor-not-allowed
    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
    ${isFocused ? 'border-blue-500 shadow-lg shadow-blue-100' : 'border-gray-300'}
    ${error ? 'border-red-500 ring-2 ring-red-200' : ''}
    ${hasValue ? 'border-gray-400' : ''}
    ${className}
  `;

  return (
    <div className={`transition-all duration-300 ${error ? 'animate-shake' : ''}`}>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-gray-700 mb-1.5 transition-colors"
      >
        {label}
        {required && <span className="text-red-500 ml-1" aria-label="required">*</span>}
      </label>

      {isTextarea ? (
        <textarea
          id={id}
          name={name}
          value={value}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          required={required}
          disabled={disabled}
          rows={rows}
          minLength={minLength}
          maxLength={maxLength}
          className={inputClasses}
          placeholder={placeholder}
          aria-describedby={helpText ? `${id}-help` : undefined}
          aria-invalid={!!error}
        />
      ) : (
        <input
          type={type}
          id={id}
          name={name}
          value={value}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          required={required}
          disabled={disabled}
          minLength={minLength}
          maxLength={maxLength}
          className={inputClasses}
          placeholder={placeholder}
          aria-describedby={helpText ? `${id}-help` : undefined}
          aria-invalid={!!error}
        />
      )}

      {helpText && (
        <p id={`${id}-help`} className="mt-1.5 text-sm text-gray-500 flex justify-between">
          <span>{helpText}</span>
          {maxLength && (
            <span className={`${value.length > maxLength * 0.9 ? 'text-red-600 font-medium' : 'text-gray-400'}`}>
              {value.length}/{maxLength}
            </span>
          )}
        </p>
      )}

      {error && (
        <p className="mt-1.5 text-sm text-red-600 flex items-center animate-slide-in">
          <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
};

/**
 * Animated select dropdown
 */
const AnimatedSelect = ({
  label,
  id,
  name,
  value,
  onChange,
  options,
  disabled = false,
  helpText,
  error
}) => {
  const [isFocused, setIsFocused] = useState(false);

  const selectClasses = `
    w-full px-4 py-2.5 border rounded-lg bg-white appearance-none cursor-pointer
    transition-all duration-200 ease-out
    disabled:bg-gray-100 disabled:cursor-not-allowed
    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
    ${isFocused ? 'border-blue-500 shadow-lg shadow-blue-100' : 'border-gray-300'}
    ${error ? 'border-red-500 ring-2 ring-red-200' : ''}
  `;

  return (
    <div className={`transition-all duration-300 ${error ? 'animate-shake' : ''}`}>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-gray-700 mb-1.5"
      >
        {label}
      </label>

      <div className="relative">
        <select
          id={id}
          name={name}
          value={value}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          disabled={disabled}
          className={selectClasses}
          aria-describedby={helpText ? `${id}-help` : undefined}
          aria-invalid={!!error}
        >
          {options.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Custom dropdown arrow */}
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
          <svg
            className={`w-5 h-5 transition-transform duration-200 ${isFocused ? 'text-blue-500 rotate-180' : 'text-gray-400'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {helpText && (
        <p id={`${id}-help`} className="mt-1.5 text-sm text-gray-500">
          {helpText}
        </p>
      )}
    </div>
  );
};

/**
 * Success Checkmark Animation
 */
const SuccessCheckmark = ({ onReset }) => {
  useEffect(() => {
    // Log success event
    if (window.gtag) {
      window.gtag('event', 'form_success', {
        event_category: 'Support',
        event_label: 'form_submitted'
      });
    }
  }, []);

  return (
    <div className="relative">
      <Confetti />

      <div className="relative z-10 max-w-2xl mx-auto p-8 bg-white rounded-2xl shadow-2xl text-center animate-scale-in">
        {/* Animated checkmark circle */}
        <div className="relative w-24 h-24 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full bg-green-100 animate-ping opacity-30" />
          <div className="relative w-24 h-24 rounded-full bg-green-100 flex items-center justify-center">
            <svg
              className="w-12 h-12 text-green-600 animate-bounce-slow"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={3}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>

        <h2 className="text-3xl font-bold text-gray-900 mb-4 animate-slide-up">
          Thank You!
        </h2>

        <p className="text-lg text-gray-600 mb-8 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          Your support request has been submitted successfully. Check your email shortly!
        </p>

        <div
          className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 mb-8 border border-blue-100 animate-slide-up"
          style={{ animationDelay: '0.2s' }}
        >
          <p className="text-sm text-blue-600 uppercase tracking-wider font-semibold mb-3">
            Your Ticket ID
          </p>
          <p className="text-4xl font-mono font-bold text-blue-700 break-all animate-fade-in" style={{ animationDelay: '0.3s' }}>
            {ticketId}
          </p>
          <p className="text-sm text-gray-500 mt-3">
            Save this ticket ID to check your request status anytime.
          </p>
        </div>

        <div
          className="bg-gray-50 rounded-xl p-6 mb-8 text-left animate-slide-up"
          style={{ animationDelay: '0.4s' }}
        >
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center">
            <svg className="w-5 h-5 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            What happens next?
          </h3>
          <ul className="space-y-2 text-gray-600">
            <li className="flex items-start">
              <span className="text-green-500 mr-2">✓</span>
              <span>Our <strong>AI assistant</strong> will analyze your request</span>
            </li>
            <li className="flex items-start">
              <span className="text-blue-500 mr-2">📧</span>
              <span>You&apos;ll receive an <strong>email response</strong> within 5 minutes</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-500 mr-2">↔️</span>
              <span>Reply directly to continue the conversation</span>
            </li>
            <li className="flex items-start">
              <span className="text-orange-500 mr-2">⚡</span>
              <span>Urgent issues are <strong>auto-escalated</strong> to human agents</span>
            </li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center animate-slide-up" style={{ animationDelay: '0.5s' }}>
          <button
            onClick={onReset}
            className="px-8 py-3.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl hover:from-blue-700 hover:to-blue-800 active:scale-95 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 flex items-center justify-center gap-2"
            aria-label="Submit another support request"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Submit Another Request
          </button>

          <button
            onClick={() => window.open('/help', '_blank')}
            className="px-8 py-3.5 bg-white border-2 border-gray-200 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 hover:border-gray-300 active:scale-95 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Visit Help Center
          </button>
        </div>

        <p className="text-xs text-gray-400 mt-6 animate-fade-in" style={{ animationDelay: '0.6s' }}>
          Need immediate help? Call us at 1-800-FLOWSYNC (toll-free)
        </p>
      </div>
    </div>
  );
};

// ----------------------------------------------------------------------------
// Main Component
// ----------------------------------------------------------------------------

/**
 * SupportForm component - renders the complete support request form with animations
 *
 * @param {Object} props
 * @param {string} props.apiEndpoint - API endpoint for form submission (default: '/api/support/submit')
 */
export default function SupportForm({ apiEndpoint = '/api/support/submit' }) {
  // State
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    category: 'general',
    priority: 'medium',
    message: ''
  });

  const [status, setStatus] = useState('idle'); // idle, submitting, success, error
  const [ticketId, setTicketId] = useState(null);
  const [error, setError] = useState(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // Stagger animation on mount
  useEffect(() => {
    const timer = setTimeout(() => setIsInitialLoad(false), 100);
    return () => clearTimeout(timer);
  }, []);

  // ------------------------------------------------------------------------
  // Event Handlers
  // ------------------------------------------------------------------------

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error when user starts typing
    if (error) setError(null);
  };

  const validateForm = () => {
    const errors = [];

    // Name validation
    if (formData.name.trim().length < 2) {
      errors.push('Please enter your full name (at least 2 characters)');
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      errors.push('Please enter a valid email address');
    }

    // Subject validation
    if (formData.subject.trim().length < 5) {
      errors.push('Please enter a subject (at least 5 characters)');
    }

    // Message validation
    if (formData.message.trim().length < 10) {
      errors.push('Please describe your issue in detail (at least 10 characters)');
    }
    if (formData.message.length > MAX_MESSAGE_LENGTH) {
      errors.push(`Message is too long (maximum ${MAX_MESSAGE_LENGTH} characters)`);
    }

    return errors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Client-side validation
    const validationErrors = validateForm();
    if (validationErrors.length > 0) {
      setError(validationErrors[0]);
      return;
    }

    setStatus('submitting');

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}: Submission failed`);
      }

      const data = await response.json();
      setTicketId(data.ticket_id);
      setStatus('success');

      // Reset form for new submission
      setFormData({
        name: '',
        email: '',
        subject: '',
        category: 'general',
        priority: 'medium',
        message: ''
      });

      // Track conversion
      if (window.gtag) {
        window.gtag('event', 'form_submit', {
          event_category: 'Support',
          event_label: data.ticket_id
        });
      }
    } catch (err) {
      console.error('Form submission error:', err);
      setError(err.message || 'Submission failed. Please try again or contact support directly.');
      setStatus('idle');
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setTicketId(null);
    setError(null);
    setFormData({
      name: '',
      email: '',
      subject: '',
      category: 'general',
      priority: 'medium',
      message: ''
    });
  };

  // ------------------------------------------------------------------------
  // Render Helpers
  // ------------------------------------------------------------------------

  const renderSuccess = () => (
    <div className="max-w-2xl mx-auto p-8 bg-white rounded-2xl shadow-2xl text-center animate-fade-in">
      {/* Animated checkmark circle */}
      <div className="relative w-24 h-24 mx-auto mb-6 animate-scale-in">
        <div className="absolute inset-0 rounded-full bg-green-400 opacity-20 animate-ping" />
        <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-green-100 to-green-50 flex items-center justify-center border-4 border-green-200 shadow-lg">
          <svg
            className="w-12 h-12 text-green-600 animate-bounce"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={3}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
      </div>

      <h2 className="text-4xl font-bold text-gray-900 mb-4 animate-slide-up">
        Request Submitted!
      </h2>

      <p className="text-lg text-gray-600 mb-8 max-w-md mx-auto animate-fade-in" style={{ animationDelay: '0.1s' }}>
        Thanks for reaching out! Our AI support assistant is already working on your request.
      </p>

      <div
        className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 rounded-xl p-8 mb-8 border-2 border-blue-100 animate-slide-up shadow-inner"
        style={{ animationDelay: '0.2s' }}
      >
        <p className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">
          Your Ticket ID
        </p>
        <p className="text-4xl font-mono font-bold text-blue-800 tracking-wider break-all animate-pulse-slow">
          {ticketId}
        </p>
        <p className="text-sm text-gray-500 mt-3">
          Save this ID to track your request status.
        </p>
      </div>

      <div
        className="bg-gray-50 rounded-xl p-6 mb-8 text-left animate-slide-up border border-gray-100"
        style={{ animationDelay: '0.3s' }}
      >
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center text-lg">
          <svg className="w-6 h-6 mr-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          What happens next?
        </h3>
        <ul className="space-y-3 text-gray-700">
          {[
            { icon: '🤖', text: 'AI assistant analyzes your request', color: 'text-blue-600' },
            { icon: '📧', text: 'Response sent to your email within 5 minutes', color: 'text-green-600' },
            { icon: '💬', text: 'Reply directly to continue the conversation', color: 'text-purple-600' },
            { icon: '👤', text: 'Complex issues escalated to human experts', color: 'text-orange-600' }
          ].map((item, idx) => (
            <li key={idx} className="flex items-start animate-fade-in" style={{ animationDelay: `${0.4 + idx * 0.1}s` }}>
              <span className={`mr-3 text-xl ${item.color}`}>{item.icon}</span>
              <span className="text-base">{item.text}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 justify-center animate-slide-up" style={{ animationDelay: '0.8s' }}>
        <button
          onClick={handleReset}
          className="px-8 py-3.5 bg-gradient-to-r from-blue-600 via-blue-700 to-blue-600 text-white rounded-xl font-semibold shadow-lg hover:shadow-2xl hover:from-blue-700 hover:via-blue-800 hover:to-blue-700 active:scale-95 transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-blue-500 focus:ring-offset-2 flex items-center justify-center gap-2 transform hover:-translate-y-0.5"
          aria-label="Submit another support request"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Submit Another Request
        </button>

        <button
          onClick={() => window.open('/help', '_blank')}
          className="px-8 py-3.5 bg-white border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 hover:border-gray-400 hover:shadow-md active:scale-95 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Help Center
        </button>
      </div>
    </div>
  );

  const renderForm = () => {
    const categoriesWithIcons = CATEGORIES.map(cat => ({
      ...cat,
      icon: cat.icon
    }));

    return (
      <div className={`max-w-2xl mx-auto p-6 md:p-8 bg-white rounded-2xl shadow-xl animate-fade-in ${isInitialLoad ? 'opacity-0' : 'opacity-100'}`}>
        {/* Header */}
        <div className="mb-8 text-center animate-slide-up">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192L5.636 18.364M12 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Contact Support</h1>
          <p className="text-gray-600 max-w-md mx-auto">
            Our AI-powered support team is here to help. Describe your issue and we&apos;ll respond within minutes.
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            className="mb-6 p-4 bg-red-50 border-2 border-red-200 rounded-xl text-red-700 flex items-start animate-shake"
            role="alert"
            aria-live="polite"
          >
            <div className="flex-shrink-0 mr-3">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="font-semibold">Oops! Something went wrong</h3>
              <p className="mt-1">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          {/* Name and Email Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
              <AnimatedInput
                label="Your Name"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                disabled={status === 'submitting'}
                placeholder="John Doe"
                helpText="Your full name"
                minLength={2}
                maxLength={200}
                error={error && error.toLowerCase().includes('name') ? error : null}
              />
            </div>

            <div className="animate-slide-up" style={{ animationDelay: '0.15s' }}>
              <AnimatedInput
                label="Email Address"
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
                disabled={status === 'submitting'}
                placeholder="john@example.com"
                helpText="We&apos;ll send your response here"
                error={error && error.toLowerCase().includes('email') ? error : null}
              />
            </div>
          </div>

          {/* Subject */}
          <div className="animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <AnimatedInput
              label="Subject"
              id="subject"
              name="subject"
              value={formData.subject}
              onChange={handleChange}
              required
              disabled={status === 'submitting'}
              placeholder="Brief description of your issue"
              helpText="What do you need help with?"
              minLength={5}
              maxLength={300}
              error={error && error.toLowerCase().includes('subject') ? error : null}
            />
          </div>

          {/* Category and Priority */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-slide-up" style={{ animationDelay: '0.25s' }}>
            <div>
              <AnimatedSelect
                label="Category"
                id="category"
                name="category"
                value={formData.category}
                onChange={handleChange}
                options={categoriesWithIcons}
                disabled={status === 'submitting'}
                helpText="Select the category that best fits"
                error={error && error.toLowerCase().includes('category') ? error : null}
              />
            </div>

            <div>
              <AnimatedSelect
                label="Priority"
                id="priority"
                name="priority"
                value={formData.priority}
                onChange={handleChange}
                options={PRIORITIES}
                disabled={status === 'submitting'}
                error={error && error.toLowerCase().includes('priority') ? error : null}
              />
            </div>
          </div>

          {/* Message */}
          <div className="animate-slide-up" style={{ animationDelay: '0.3s' }}>
            <AnimatedInput
              label="How can we help you?"
              id="message"
              name="message"
              value={formData.message}
              onChange={handleChange}
              required
              disabled={status === 'submitting'}
              rows={6}
              placeholder="Please describe your issue in detail. Include steps to reproduce, error messages, and what you expected to happen."
              helpText="The more detail you provide, the faster we can help."
              isTextarea={true}
              error={error && error.toLowerCase().includes('message') ? error : null}
            />
          </div>

          {/* Character count progress bar */}
          {formData.message.length > 0 && (
            <div className="animate-slide-up" style={{ animationDelay: '0.35s' }}>
              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    formData.message.length > MAX_MESSAGE_LENGTH * 0.9
                      ? 'bg-red-500'
                      : formData.message.length > MAX_MESSAGE_LENGTH * 0.7
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min((formData.message.length / MAX_MESSAGE_LENGTH) * 100, 100)}%` }}
                  role="progressbar"
                  aria-valuenow={formData.message.length}
                  aria-valuemin={0}
                  aria-valuemax={MAX_MESSAGE_LENGTH}
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="pt-2 animate-slide-up" style={{ animationDelay: '0.4s' }}>
            <button
              type="submit"
              disabled={status === 'submitting'}
              className={`
                w-full py-4 px-6 rounded-xl font-semibold text-white
                shadow-lg transition-all duration-200
                focus:outline-none focus:ring-4 focus:ring-blue-500 focus:ring-offset-2
                active:scale-95 disabled:cursor-not-allowed
                ${status === 'submitting'
                  ? 'bg-gradient-to-r from-gray-400 to-gray-500 cursor-wait'
                  : 'bg-gradient-to-r from-blue-600 via-blue-700 to-blue-600 hover:from-blue-700 hover:via-blue-800 hover:to-blue-700 hover:shadow-2xl hover:-translate-y-0.5'
                }
              `}
              aria-busy={status === 'submitting'}
            >
              {status === 'submitting' ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-6 w-6 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  <span className="text-lg">Processing Your Request...</span>
                </span>
              ) : (
                <span className="flex items-center justify-center text-lg">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  Submit Support Request
                </span>
              )}
            </button>
          </div>

          {/* Privacy notice */}
          <div className="text-center text-sm text-gray-500 pt-4 border-t border-gray-100 animate-fade-in" style={{ animationDelay: '0.5s' }}>
            <p>
              By submitting, you agree to our{' '}
              <a href="/privacy" className="text-blue-600 hover:underline font-medium transition-colors">Privacy Policy</a>
              {' '}and{' '}
              <a href="/terms" className="text-blue-600 hover:underline font-medium transition-colors">Terms of Service</a>.
            </p>
            <p className="mt-2 text-xs text-gray-400">
              🔒 Your information is secure and encrypted.
            </p>
          </div>
        </form>
      </div>
    );
  };

  // ------------------------------------------------------------------------
  // Main Render
  // ------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-indigo-50 py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000" />
      </div>

      <div className="relative z-10">
        {status === 'success' ? (
          <div className="fixed inset-0 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 -z-10">
            <Confetti />
          </div>
        ) : null}

        {status === 'success' ? (
          <div className="animate-scale-in">
            {renderSuccess()}
          </div>
        ) : (
          renderForm()
        )}
      </div>

      {/* Global animation styles */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(-10px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes scaleIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes bounceSlow {
          0%, 100% { transform: translateY(-5%); }
          50% { transform: translateY(0); }
        }
        @keyframes confetti {
          0% { transform: translateY(0) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }

        .animate-fade-in { animation: fadeIn 0.5s ease-out forwards; }
        .animate-slide-up { animation: slideUp 0.4s ease-out forwards; animation-fill-mode: both; }
        .animate-slide-in { animation: slideIn 0.3s ease-out forwards; }
        .animate-scale-in { animation: scaleIn 0.4s ease-out forwards; }
        .animate-bounce-slow { animation: bounceSlow 2s infinite; }
        .animate-pulse-slow { animation: pulse 3s ease-in-out infinite; }
        .animate-shake { animation: shake 0.4s ease-in-out; }
        .animate-confetti { animation: confetti 4s ease-out forwards; }
        .animate-blob { animation: blob 7s infinite ease-in-out; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-4000 { animation-delay: 4s; }

        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
          20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
      `}</style>
    </div>
  );
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ScrollToPlugin } from 'gsap/ScrollToPlugin';
import {
  RiQuillPenLine,
  RiSearchEyeLine,
  RiFileTextLine,
  RiGitBranchLine,
  RiMacLine,
  RiCodeSSlashLine,
  RiBookOpenLine,
  RiLightbulbLine,
  RiShieldCheckLine,
  RiArrowRightLine,
  RiCheckLine,
  RiSparklingLine,
  RiTerminalBoxLine,
  RiTableLine,
  RiImageLine,
  RiFlowChart,
  RiMenuLine,
  RiCloseLine,
} from '@remixicon/react';

gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const workflowRef = useRef<HTMLDivElement>(null);
  const agentRef = useRef<HTMLDivElement>(null);
  const researchRef = useRef<HTMLDivElement>(null);
  const writingRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);

  // Animation started refs (to prevent re-triggering)
  const agentAnimStarted = useRef(false);
  const vibeAnimStarted = useRef(false);
  const writingAnimStarted = useRef(false);

  const [isLoaded, setIsLoaded] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Hero animation states
  const [typedText, setTypedText] = useState('');
  const [animationPhase, setAnimationPhase] = useState(0); // 0: typing, 1: processing, 2: complete
  const [papersFound, setPapersFound] = useState(0);
  const [processingTime, setProcessingTime] = useState(0);
  const fullText = 'Find papers about world models in surgical robotics';

  // AI Agent section animation states
  const [agentTypedText, setAgentTypedText] = useState('');
  const [agentPhase, setAgentPhase] = useState(0); // 0: waiting, 1: typing, 2: tool, 3: code typing, 4: complete
  const [agentCodeLines, setAgentCodeLines] = useState(0);
  const agentFullText = 'Add a comparison table for the three methods in Section 3';

  // Vibe Research section animation states
  const [vibePhase, setVibePhase] = useState(0); // 0: waiting, 1: searching, 2: analyzing, 3: complete
  const [vibePapers, setVibePapers] = useState(0);
  const [vibeThemes, setVibeThemes] = useState(0);
  const [vibeGaps, setVibeGaps] = useState(0);
  const [vibeHypotheses, setVibeHypotheses] = useState(0);

  // Writing Intelligence section animation states
  const [writingPhase, setWritingPhase] = useState(0); // 0: waiting, 1: showing deletions, 2: showing additions, 3: complete
  const [deletionLines, setDeletionLines] = useState(0);
  const [additionLines, setAdditionLines] = useState(0);

  // Smooth scroll handler
  const scrollToSection = (sectionId: string) => {
    gsap.to(window, {
      duration: 1,
      scrollTo: { y: sectionId, offsetY: 80 },
      ease: 'power3.inOut',
    });
    setMobileMenuOpen(false);
  };

  useEffect(() => {
    setIsLoaded(true);

    // Scroll progress indicator
    const updateProgress = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = (scrollTop / docHeight) * 100;
      setScrollProgress(progress);
    };
    window.addEventListener('scroll', updateProgress);

    // Refresh ScrollTrigger after hydration
    const refreshTimeout = setTimeout(() => {
      ScrollTrigger.refresh();
    }, 100);

    // Hero animations (these work fine - no scroll trigger)
    const heroCtx = gsap.context(() => {
      gsap.from('.hero-badge', {
        y: -20,
        opacity: 0,
        duration: 0.6,
        ease: 'power3.out',
      });

      gsap.from('.hero-title', {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.2,
        ease: 'power3.out',
      });

      gsap.from('.hero-subtitle', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.4,
        ease: 'power3.out',
      });

      gsap.from('.hero-cta', {
        y: 20,
        opacity: 0,
        duration: 0.6,
        delay: 0.6,
        ease: 'power3.out',
      });

      gsap.from('.hero-visual', {
        y: 60,
        opacity: 0,
        duration: 1,
        delay: 0.8,
        ease: 'power3.out',
      });
    }, heroRef);

    // Hero typing and processing animation sequence
    const startHeroAnimation = () => {
      // Phase 0: Typing animation
      let charIndex = 0;
      const typingInterval = setInterval(() => {
        if (charIndex <= fullText.length) {
          setTypedText(fullText.slice(0, charIndex));
          charIndex++;
        } else {
          clearInterval(typingInterval);
          // Move to processing phase
          setTimeout(() => {
            setAnimationPhase(1);
            // Start processing animation - tool calls appear over time
            let time = 0;

            const processingInterval = setInterval(() => {
              time += 0.1;
              setProcessingTime(time);
            }, 100);

            // Complete after 3.5 seconds (enough for all 5 tools to appear and complete)
            setTimeout(() => {
              clearInterval(processingInterval);
              setPapersFound(48);
              setAnimationPhase(2);
            }, 3500);
          }, 400);
        }
      }, 50);
    };

    // Start hero animation after initial load
    const heroAnimTimeout = setTimeout(startHeroAnimation, 1200);

    // Simplified scroll animations using ScrollTrigger batch
    ScrollTrigger.batch('.feature-card, .workflow-step, .writing-tool', {
      onEnter: (elements) => {
        gsap.to(elements, {
          opacity: 1,
          y: 0,
          stagger: 0.1,
          duration: 0.5,
          ease: 'power3.out',
        });
      },
      start: 'top 90%',
      once: true,
    });

    // Set initial state for batch elements
    gsap.set('.feature-card, .workflow-step, .writing-tool', {
      opacity: 0,
      y: 30,
    });

    // Simple fade-in for other sections
    ScrollTrigger.batch('.agent-content, .agent-visual, .research-content, .research-visual, .cta-content', {
      onEnter: (elements) => {
        gsap.to(elements, {
          opacity: 1,
          x: 0,
          y: 0,
          duration: 0.6,
          ease: 'power3.out',
        });
      },
      start: 'top 85%',
      once: true,
    });

    gsap.set('.agent-content, .research-visual', { opacity: 0, x: -30 });
    gsap.set('.agent-visual, .research-content', { opacity: 0, x: 30 });
    gsap.set('.cta-content', { opacity: 0, y: 30 });

    // AI Agent section scroll-triggered animation
    const agentAnimation = () => {
      if (agentAnimStarted.current) return; // Already started
      agentAnimStarted.current = true;
      setAgentPhase(1);
      let charIndex = 0;
      const typingInterval = setInterval(() => {
        if (charIndex <= agentFullText.length) {
          setAgentTypedText(agentFullText.slice(0, charIndex));
          charIndex++;
        } else {
          clearInterval(typingInterval);
          setTimeout(() => {
            setAgentPhase(2); // Show tool call
            setTimeout(() => {
              setAgentPhase(3); // Start code typing
              let line = 0;
              const codeInterval = setInterval(() => {
                line++;
                setAgentCodeLines(line);
                if (line >= 12) {
                  clearInterval(codeInterval);
                  setAgentPhase(4);
                }
              }, 80);
            }, 800);
          }, 400);
        }
      }, 40);
    };

    // Vibe Research section scroll-triggered animation
    const vibeAnimation = () => {
      if (vibeAnimStarted.current) return;
      vibeAnimStarted.current = true;
      setVibePhase(1);
      let papers = 0;
      const countInterval = setInterval(() => {
        papers += Math.floor(Math.random() * 20) + 5;
        if (papers >= 366) {
          papers = 366;
          clearInterval(countInterval);
          setVibePhase(2);
          // Animate themes, gaps, hypotheses
          setTimeout(() => setVibeThemes(4), 300);
          setTimeout(() => setVibeGaps(5), 600);
          setTimeout(() => {
            setVibeHypotheses(4);
            setVibePhase(3);
          }, 900);
        }
        setVibePapers(papers);
      }, 50);
    };

    // Writing Intelligence section scroll-triggered animation
    const writingAnimation = () => {
      if (writingAnimStarted.current) return;
      writingAnimStarted.current = true;
      setWritingPhase(1);
      // Show deletions one by one
      let delLine = 0;
      const delInterval = setInterval(() => {
        delLine++;
        setDeletionLines(delLine);
        if (delLine >= 2) {
          clearInterval(delInterval);
          setTimeout(() => {
            setWritingPhase(2);
            // Show additions one by one
            let addLine = 0;
            const addInterval = setInterval(() => {
              addLine++;
              setAdditionLines(addLine);
              if (addLine >= 4) {
                clearInterval(addInterval);
                setWritingPhase(3);
              }
            }, 200);
          }, 500);
        }
      }, 300);
    };

    // Create scroll triggers for each section
    ScrollTrigger.create({
      trigger: '#agent',
      start: 'top 70%',
      once: true,
      onEnter: agentAnimation,
    });

    ScrollTrigger.create({
      trigger: '#research',
      start: 'top 70%',
      once: true,
      onEnter: vibeAnimation,
    });

    ScrollTrigger.create({
      trigger: '#writing',
      start: 'top 70%',
      once: true,
      onEnter: writingAnimation,
    });

    return () => {
      window.removeEventListener('scroll', updateProgress);
      clearTimeout(refreshTimeout);
      clearTimeout(heroAnimTimeout);
      heroCtx.revert();
      ScrollTrigger.getAll().forEach(trigger => trigger.kill());
    };
  }, []);

  const features = [
    {
      icon: RiSearchEyeLine,
      title: 'Vibe Research Engine',
      description: 'Autonomous research mode that explores Google Scholar, Semantic Scholar, and arXiv.',
    },
    {
      icon: RiSparklingLine,
      title: 'AI Research Agent',
      description: 'Intelligent agent that searches literature, analyzes papers, and discovers research gaps.',
    },
    {
      icon: RiQuillPenLine,
      title: 'Professional LaTeX Editor',
      description: 'Monaco-powered editor with syntax highlighting, autocomplete, and real-time error detection.',
    },
    {
      icon: RiMacLine,
      title: 'Local-First & Private',
      description: 'Your documents stay on your machine. No cloud uploads, complete privacy.',
    },
    {
      icon: RiGitBranchLine,
      title: 'Git & Overleaf Sync',
      description: 'Seamlessly sync with Git repositories or collaborate via Overleaf integration.',
    },
    {
      icon: RiShieldCheckLine,
      title: 'Offline Capable',
      description: 'Compile LaTeX locally with Tectonic. No Docker required for basic use.',
    },
  ];

  const writingTools = [
    { icon: RiTableLine, name: 'Tables', description: 'Generate booktabs tables from CSV or markdown' },
    { icon: RiImageLine, name: 'Figures', description: 'Create TikZ and pgfplots visualizations' },
    { icon: RiFlowChart, name: 'Algorithms', description: 'Generate algorithm2e pseudocode blocks' },
    { icon: RiBookOpenLine, name: 'Citations', description: 'Auto-add papers to .bib and insert \\cite{}' },
    { icon: RiCodeSSlashLine, name: 'Code Blocks', description: 'Syntax-highlighted code listings' },
    { icon: RiFileTextLine, name: 'Structure', description: 'Analyze and refactor document structure' },
  ];

  return (
    <div className={`min-h-screen bg-fill-secondary transition-opacity duration-500 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}>
      {/* Scroll Progress Bar */}
      <div className="fixed top-0 left-0 right-0 h-1 z-[60] bg-transparent">
        <div
          className="h-full bg-green2 transition-all duration-150"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-fill-secondary/80 backdrop-blur-lg border-b border-black/6">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-[12px] bg-green2 flex items-center justify-center">
              <RiQuillPenLine className="w-6 h-6 text-white" />
            </div>
            <span className="font-youware-sans text-xl font-semibold text-primary">YouResearch</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <button onClick={() => scrollToSection('#features')} className="typo-body text-secondary hover:text-primary transition-colors">Features</button>
            <button onClick={() => scrollToSection('#agent')} className="typo-body text-secondary hover:text-primary transition-colors">AI Agent</button>
            <button onClick={() => scrollToSection('#research')} className="typo-body text-secondary hover:text-primary transition-colors">Research</button>
            <button onClick={() => scrollToSection('#writing')} className="typo-body text-secondary hover:text-primary transition-colors">Writing Tools</button>
          </div>
          <div className="flex items-center gap-4">
            <button className="hidden sm:flex bg-green2 hover:bg-green1 text-white rounded-full px-5 py-2.5 typo-body-strong transition-colors">
              Download for Mac
            </button>
            <button
              className="md:hidden p-2 rounded-[10px] hover:bg-black/5 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? (
                <RiCloseLine className="w-6 h-6 text-primary" />
              ) : (
                <RiMenuLine className="w-6 h-6 text-primary" />
              )}
            </button>
          </div>
        </div>
        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-black/6 bg-fill-secondary/95 backdrop-blur-lg">
            <div className="px-6 py-4 space-y-2">
              <button onClick={() => scrollToSection('#features')} className="block w-full text-left py-3 typo-body text-secondary hover:text-primary transition-colors">Features</button>
              <button onClick={() => scrollToSection('#agent')} className="block w-full text-left py-3 typo-body text-secondary hover:text-primary transition-colors">AI Agent</button>
              <button onClick={() => scrollToSection('#research')} className="block w-full text-left py-3 typo-body text-secondary hover:text-primary transition-colors">Research</button>
              <button onClick={() => scrollToSection('#writing')} className="block w-full text-left py-3 typo-body text-secondary hover:text-primary transition-colors">Writing Tools</button>
              <button className="w-full bg-green2 hover:bg-green1 text-white rounded-full px-5 py-3 typo-body-strong transition-colors mt-2">
                Download for Mac
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section ref={heroRef} className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            {/* Badge */}
            <div className="hero-badge inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green3 mb-8">
              <RiSparklingLine className="w-4 h-4 text-green1" />
              <span className="typo-small-strong text-green1">Powered by Claude AI</span>
            </div>

            {/* Title */}
            <h1 className="hero-title font-youware-sans text-5xl md:text-7xl font-medium text-primary leading-tight mb-6">
              The LaTeX IDE that<br />
              <span className="text-green2">researches with you</span>
            </h1>

            {/* Subtitle */}
            <p className="hero-subtitle typo-ex-large text-secondary max-w-2xl mx-auto mb-10">
              YouResearch is a local-first macOS app that combines a professional LaTeX editor
              with an AI research agent. Explore literature deeper, discover ideas faster.
            </p>

            {/* CTAs */}
            <div className="hero-cta flex flex-col sm:flex-row items-center justify-center gap-4">
              <button className="flex items-center gap-2 bg-green2 hover:bg-green1 text-white rounded-full px-8 py-4 typo-body-strong transition-all hover:shadow-lg hover:-translate-y-0.5">
                <RiMacLine className="w-5 h-5" />
                Download for macOS
              </button>
              <button className="flex items-center gap-2 border border-black/10 bg-white hover:bg-black/3 rounded-full px-8 py-4 typo-body transition-colors">
                View on GitHub
                <RiArrowRightLine className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Hero Visual - App Screenshot with Animations */}
          <div className="hero-visual mt-16 relative">
            <div className="rounded-[30px] border border-black/10 bg-white shadow-2xl overflow-hidden">
              {/* Mock App Window */}
              <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-black/6">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 text-center typo-small text-tertiary">YouResearch — main.tex</div>
              </div>
              <div className="flex h-[500px]">
                {/* Sidebar */}
                <div className="w-56 bg-sidebar-bg border-r border-black/6 p-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green2/10">
                      <RiFileTextLine className="w-4 h-4 text-green2" />
                      <span className="typo-small text-primary">main.tex</span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-black/3">
                      <RiFileTextLine className="w-4 h-4 text-secondary" />
                      <span className="typo-small text-secondary">references.bib</span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-black/3">
                      <RiFileTextLine className="w-4 h-4 text-secondary" />
                      <span className="typo-small text-secondary">figures/</span>
                    </div>
                  </div>
                </div>
                {/* Editor */}
                <div className="flex-1 bg-editor-bg p-4 font-mono text-sm text-editor-text">
                  <pre className="leading-relaxed">
{`\\documentclass{article}
\\usepackage{amsmath,graphicx}

\\title{World Models in Surgical Robotics}
\\author{Your Name}

\\begin{document}
\\maketitle

\\section{Introduction}
Recent advances in world models
have revolutionized surgical robotics...

\\section{Related Work}
\\cite{foundation2024}
introduced the foundation model...`}
                  </pre>
                </div>
                {/* Chat Panel with Animations */}
                <div className="w-80 border-l border-black/6 bg-white p-4 overflow-y-auto">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-8 h-8 rounded-full bg-green2 flex items-center justify-center">
                      <RiSparklingLine className="w-5 h-5 text-white" />
                    </div>
                    <span className="typo-body-strong text-primary">AI Agent</span>
                  </div>
                  <div className="space-y-3">
                    {/* User message with typing effect */}
                    <div className={`bg-gray-100 rounded-[16px] p-3 ml-6 transition-all duration-500 ${animationPhase >= 0 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <p className="typo-small text-primary">
                        {typedText}
                        {animationPhase === 0 && <span className="inline-block w-0.5 h-4 bg-primary ml-0.5 animate-pulse" />}
                      </p>
                    </div>
                    {/* Agent response with tool calls */}
                    {animationPhase >= 1 && (
                      <div className="bg-green3/50 rounded-[16px] p-3 animate-fade-in-up">
                        <div className="flex items-start gap-2 mb-3">
                          <RiSparklingLine className="w-4 h-4 text-green2 mt-0.5 flex-shrink-0" />
                          <p className="typo-small text-primary">I&apos;ll search for relevant papers on world models in surgical robotics.</p>
                        </div>
                        {/* Tool calls appearing one by one */}
                        <div className="space-y-1.5">
                          {[
                            'search_google_scholar',
                            'search_semantic_scholar',
                            'search_arxiv',
                            'think',
                            'read_paper',
                          ].map((tool, i) => {
                            const toolDelay = 0.5 + i * 0.6;
                            const showTool = processingTime >= toolDelay;
                            const toolComplete = processingTime >= toolDelay + 0.4;
                            return showTool ? (
                              <div
                                key={i}
                                className="flex items-center justify-between bg-white/60 rounded-lg px-2.5 py-1.5 animate-fade-in-up"
                                style={{ animationDelay: `${i * 0.1}s` }}
                              >
                                <div className="flex items-center gap-2">
                                  <RiArrowRightLine className="w-3 h-3 text-tertiary" />
                                  <code className="typo-ex-small text-primary">{tool}</code>
                                </div>
                                {toolComplete ? (
                                  <div className="w-4 h-4 rounded-full bg-green2 flex items-center justify-center">
                                    <RiCheckLine className="w-2.5 h-2.5 text-white" />
                                  </div>
                                ) : (
                                  <div className="w-4 h-4 rounded-full border-2 border-green2 border-t-transparent animate-spin" />
                                )}
                              </div>
                            ) : null;
                          })}
                        </div>
                        {/* Final message */}
                        {animationPhase >= 2 && (
                          <p className="typo-small text-primary mt-3 animate-fade-in-up">
                            Found {papersFound} relevant papers. How would you like me to proceed?
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            {/* Glow effect */}
            <div className="absolute -inset-4 bg-gradient-to-r from-green3/40 via-transparent to-green3/40 rounded-[40px] -z-10 blur-3xl" />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" ref={featuresRef} className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-2 rounded-full bg-green3 typo-small-strong text-green1 mb-4">
              Features
            </span>
            <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-4">
              Everything you need to research
            </h2>
            <p className="typo-large text-secondary max-w-2xl mx-auto">
              A complete toolkit for academic research, from discovery to publication.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <div
                key={index}
                className="feature-card group rounded-[30px] border border-black/6 bg-white p-8 transition-all duration-300 hover:border-green2/20 hover:shadow-lg hover:-translate-y-1"
              >
                <div className="inline-flex rounded-[16px] p-4 mb-6 bg-green2/10 group-hover:bg-green2 transition-colors duration-300">
                  <feature.icon className="w-8 h-8 text-green2 group-hover:text-white transition-colors" />
                </div>
                <h3 className="typo-h2 text-primary mb-3">{feature.title}</h3>
                <p className="typo-body text-secondary">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Animated Workflow Section */}
      <section ref={workflowRef} className="py-24 px-6 bg-white overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-2 rounded-full bg-orange2/20 typo-small-strong text-orange1 mb-4">
              How It Works
            </span>
            <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-4">
              From idea to publication
            </h2>
            <p className="typo-large text-secondary max-w-2xl mx-auto">
              YouResearch accelerates every stage of academic research.
            </p>
          </div>

          {/* Workflow Timeline */}
          <div className="relative">
            {/* Connection Line */}
            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-green2 via-green2 to-transparent hidden lg:block" />

            <div className="space-y-12 lg:space-y-0 lg:grid lg:grid-cols-4 lg:gap-8 lg:items-stretch">
              {[
                {
                  step: '01',
                  title: 'Research',
                  description: 'Explore literature with Vibe Research. Find papers, track citations, identify gaps.',
                  icon: RiSearchEyeLine,
                  color: 'bg-purple-500',
                },
                {
                  step: '02',
                  title: 'Write',
                  description: 'Draft in LaTeX with AI assistance. Generate tables, figures, and equations.',
                  icon: RiQuillPenLine,
                  color: 'bg-blue-500',
                },
                {
                  step: '03',
                  title: 'Compile',
                  description: 'Build PDFs locally with Tectonic. Fix errors automatically with AI.',
                  icon: RiTerminalBoxLine,
                  color: 'bg-green-500',
                },
                {
                  step: '04',
                  title: 'Publish',
                  description: 'Sync with Overleaf or push to Git. Share with collaborators instantly.',
                  icon: RiGitBranchLine,
                  color: 'bg-orange-500',
                },
              ].map((item, index) => (
                <div key={index} className="relative h-full">
                  <div className="workflow-step bg-fill-secondary rounded-[24px] p-6 h-full hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
                    <div className={`w-12 h-12 rounded-[14px] ${item.color} flex items-center justify-center mb-4`}>
                      <item.icon className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="typo-small text-tertiary">{item.step}</span>
                      <h3 className="typo-h2 text-primary">{item.title}</h3>
                    </div>
                    <p className="typo-body text-secondary">{item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* AI Agent Section */}
      <section id="agent" ref={agentRef} className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="agent-content">
              <span className="inline-block px-4 py-2 rounded-full bg-green3 typo-small-strong text-green1 mb-6">
                AI Agent
              </span>
              <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-6">
                Your AI research partner
              </h2>
              <p className="typo-large text-secondary mb-8">
                The YouResearch agent understands LaTeX and academic research. It can search literature,
                analyze papers, manage citations, and help you structure your arguments.
              </p>
              <ul className="space-y-4">
                {[
                  'Read and edit any file in your project',
                  'Search Google Scholar, Semantic Scholar, and arXiv',
                  'Auto-generate tables, figures, and algorithms',
                  'Fix LaTeX compilation errors automatically',
                  'Structured planning for complex revisions',
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <div className="mt-1 w-5 h-5 rounded-full bg-green2 flex items-center justify-center flex-shrink-0">
                      <RiCheckLine className="w-3 h-3 text-white" />
                    </div>
                    <span className="typo-body text-primary">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="agent-visual">
              <div className="rounded-[30px] border border-black/6 bg-fill-secondary p-8">
                <div className="space-y-4">
                  {/* User message with typing animation */}
                  <div className={`flex justify-end transition-all duration-500 ${agentPhase >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                    <div className="bg-white border border-black/6 rounded-[20px] rounded-br-[8px] p-4 max-w-[80%]">
                      <p className="typo-body text-primary">
                        {agentTypedText}
                        {agentPhase === 1 && <span className="inline-block w-0.5 h-4 bg-primary ml-0.5 animate-pulse" />}
                      </p>
                    </div>
                  </div>
                  {/* Agent response with tool call */}
                  {agentPhase >= 2 && (
                    <div className="flex items-start gap-3 animate-fade-in-up">
                      <div className="w-8 h-8 rounded-full bg-green2 flex items-center justify-center flex-shrink-0">
                        <RiSparklingLine className="w-5 h-5 text-white" />
                      </div>
                      <div className="bg-white border border-black/6 rounded-[20px] rounded-tl-[8px] p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <RiTerminalBoxLine className="w-4 h-4 text-green2" />
                          <span className="typo-small-strong text-green2">Using: create_table</span>
                          {agentPhase >= 3 && (
                            <div className="w-4 h-4 rounded-full bg-green2 flex items-center justify-center ml-1">
                              <RiCheckLine className="w-2.5 h-2.5 text-white" />
                            </div>
                          )}
                          {agentPhase === 2 && (
                            <div className="w-4 h-4 rounded-full border-2 border-green2 border-t-transparent animate-spin ml-1" />
                          )}
                        </div>
                        <p className="typo-body text-primary">I&apos;ll create a booktabs table comparing accuracy, speed, and memory usage across the three methods mentioned in your paper.</p>
                      </div>
                    </div>
                  )}
                  {/* Code block with typing animation */}
                  {agentPhase >= 3 && (
                    <div className="ml-11 bg-editor-bg rounded-[16px] p-4 font-mono text-sm text-editor-text animate-fade-in-up overflow-hidden">
                      <pre className="whitespace-pre-wrap">{`\\begin{table}[h]
  \\centering
  \\begin{tabular}{lrrr}
    \\toprule
    Method & Accuracy & Speed \\\\
    \\midrule
    Baseline & 78.3\\% & 1.0x \\\\
    Ours & \\textbf{92.1\\%} & 1.2x \\\\
    \\bottomrule
  \\end{tabular}
\\end{table}`.split('\n').slice(0, agentCodeLines).join('\n')}</pre>
                      {agentPhase === 3 && <span className="inline-block w-2 h-4 bg-green2 animate-pulse" />}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Research Engine Section */}
      <section id="research" ref={researchRef} className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          {/* Section Header */}
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-2 rounded-full bg-orange2/20 typo-small-strong text-orange1 mb-4">
              Vibe Research Engine
            </span>
            <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-4">
              From topic to breakthrough ideas
            </h2>
            <p className="typo-large text-secondary max-w-3xl mx-auto">
              Enter a research topic and let the AI explore the literature autonomously. It reads papers,
              identifies themes and gaps, then generates a complete research report with novel hypotheses.
            </p>
          </div>

          {/* Visual: PDF + Research Panel side by side */}
          <div className="research-visual">
            <div className="rounded-[30px] border border-black/6 bg-fill-secondary overflow-hidden shadow-2xl">
              {/* App Header Bar */}
              <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-black/6">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 text-center typo-small text-tertiary">YouResearch — Vibe Research Report</div>
              </div>

              <div className="flex">
                {/* PDF Preview Panel */}
                <div className="w-1/2 bg-gray-200 p-6 border-r border-black/6">
                  <div className="bg-white rounded-lg shadow-lg overflow-hidden max-h-[500px]">
                    {/* PDF Page */}
                    <div className="p-8 text-center border-b border-gray-200">
                      <p className="text-gray-400 text-sm mb-4">1 / 6</p>
                      <h3 className="text-xl font-serif font-semibold text-gray-800 mb-2">Vibe Research Report:</h3>
                      <p className="text-lg font-serif text-gray-700 mb-4">world model in surgical robot manipulation</p>
                      <p className="text-sm text-gray-500 mb-1">Generated by YouResearch Vibe Research</p>
                      <p className="text-sm text-gray-500 mb-6">January 28, 2026</p>

                      <div className="text-left max-w-sm mx-auto">
                        <p className="text-xs font-bold text-gray-600 mb-2">Abstract</p>
                        <p className="text-xs text-gray-600 leading-relaxed mb-4">
                          This report presents the findings of an automated literature review on <span className="font-semibold">world model in surgical robot manipulation</span>.
                          We analyzed 366 papers, identified 4 major themes, discovered 5 research gaps, and generated 4 novel hypotheses.
                        </p>

                        <p className="text-xs font-bold text-gray-600 mb-2">Contents</p>
                        <div className="text-xs text-gray-600 space-y-1">
                          <div className="flex justify-between">
                            <span>1. Research Scope</span>
                            <span className="text-gray-400">2</span>
                          </div>
                          <div className="flex justify-between">
                            <span>2. Literature Landscape</span>
                            <span className="text-gray-400">2</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-orange1">3. Identified Research Gaps</span>
                            <span className="text-gray-400">3</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-orange1">4. Research Hypotheses</span>
                            <span className="text-gray-400">4</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Research Panel */}
                <div className="w-1/2 bg-white">
                  {/* Panel Header */}
                  <div className="px-5 py-4 border-b border-black/6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-[10px] bg-orange2 flex items-center justify-center">
                        <RiSearchEyeLine className="w-5 h-5 text-orange1" />
                      </div>
                      <span className="typo-body-strong text-primary">Research Output</span>
                    </div>
                    {vibePhase >= 3 ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-green3 typo-small-strong text-green1 animate-fade-in-up">
                        <RiCheckLine className="w-3.5 h-3.5" />
                        Complete
                      </span>
                    ) : vibePhase >= 1 ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange2/20 typo-small-strong text-orange1">
                        <div className="w-3 h-3 rounded-full border-2 border-orange1 border-t-transparent animate-spin" />
                        Analyzing...
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gray-100 typo-small-strong text-tertiary">
                        Waiting
                      </span>
                    )}
                  </div>

                  {/* Research Topic */}
                  <div className="px-5 py-3 border-b border-black/6">
                    <p className="typo-small text-secondary">Research Topic</p>
                    <p className="typo-body-strong text-primary">world model in surgical robot manipulation</p>
                    <div className="flex items-center gap-3 mt-2 typo-ex-small text-secondary">
                      <span>Papers: <span className={`text-primary font-mono transition-all ${vibePhase >= 1 ? 'opacity-100' : 'opacity-30'}`}>{vibePapers}</span></span>
                      <span>Themes: <span className={`text-primary font-mono transition-all ${vibeThemes > 0 ? 'opacity-100' : 'opacity-30'}`}>{vibeThemes}</span></span>
                      <span>Gaps: <span className={`text-primary font-mono transition-all ${vibeGaps > 0 ? 'opacity-100' : 'opacity-30'}`}>{vibeGaps}</span></span>
                      <span>Hypotheses: <span className={`text-primary font-mono transition-all ${vibeHypotheses > 0 ? 'opacity-100' : 'opacity-30'}`}>{vibeHypotheses}</span></span>
                    </div>
                  </div>

                  {/* Sections */}
                  <div className="divide-y divide-black/6 max-h-[380px] overflow-y-auto">
                    {/* Themes */}
                    <div className="px-5 py-2.5 flex items-center justify-between hover:bg-black/2">
                      <div className="flex items-center gap-2">
                        <RiArrowRightLine className="w-4 h-4 text-tertiary" />
                        <span className="typo-body text-primary">Themes</span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-fill-secondary typo-ex-small text-secondary">4</span>
                    </div>

                    {/* Gaps */}
                    <div className="px-5 py-2.5 flex items-center justify-between hover:bg-black/2">
                      <div className="flex items-center gap-2">
                        <RiArrowRightLine className="w-4 h-4 text-tertiary" />
                        <span className="typo-body text-primary">Research Gaps</span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-fill-secondary typo-ex-small text-secondary">5</span>
                    </div>

                    {/* Hypotheses - Expanded */}
                    <div className="bg-orange2/5">
                      <div className="px-5 py-2.5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4 text-orange1 rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                          <span className="typo-body-strong text-primary">Hypotheses</span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-orange2/20 typo-ex-small font-semibold text-orange1">4</span>
                      </div>

                      {/* Hypothesis 1 - Expanded */}
                      <div className="px-5 py-3 border-l-4 border-orange2 ml-4 mr-4 mb-2 bg-white rounded-r-lg">
                        <div className="flex items-start gap-2">
                          <RiLightbulbLine className="w-4 h-4 text-orange1 flex-shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="typo-small-strong text-primary truncate">Hierarchical Surgical World...</span>
                              <div className="flex gap-1 flex-shrink-0">
                                <span className="px-1 py-0.5 rounded bg-green3/70 text-[10px] font-medium text-green1">N:7</span>
                                <span className="px-1 py-0.5 rounded bg-blue-100 text-[10px] font-medium text-blue-600">F:7</span>
                                <span className="px-1 py-0.5 rounded bg-purple-100 text-[10px] font-medium text-purple-600">I:8</span>
                              </div>
                            </div>
                            <p className="typo-ex-small text-secondary line-clamp-2">
                              Propose a hierarchical world model that learns coarse-grained surgical task representations combined with fine-grained dynamics.
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Other hypotheses */}
                      {['Semantic-Visual Hybrid...', 'Meta-Learning Framework...', 'Unified Differentiable...'].map((title, i) => (
                        <div key={i} className="px-5 py-2 flex items-center gap-2 ml-4 opacity-70 hover:opacity-100">
                          <RiLightbulbLine className="w-4 h-4 text-orange1" />
                          <span className="typo-small text-secondary">{title}</span>
                          <div className="flex gap-1 ml-auto">
                            <span className="px-1 py-0.5 rounded bg-gray-100 text-[9px] text-gray-500">N:{7-i}</span>
                            <span className="px-1 py-0.5 rounded bg-gray-100 text-[9px] text-gray-500">F:{6-i}</span>
                            <span className="px-1 py-0.5 rounded bg-gray-100 text-[9px] text-gray-500">I:{8-i}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* View Report Button */}
                  <div className="px-5 py-4 border-t border-black/6">
                    <button className="w-full flex items-center justify-center gap-2 bg-green2 hover:bg-green1 text-white rounded-full py-2.5 typo-body-strong transition-colors">
                      <RiFileTextLine className="w-4 h-4" />
                      View Report
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature highlights below */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-12">
            {[
              { icon: RiBookOpenLine, title: 'Literature Synthesis', desc: 'Reads & analyzes papers' },
              { icon: RiSearchEyeLine, title: 'Gap Detection', desc: 'Finds unexplored areas' },
              { icon: RiLightbulbLine, title: 'Hypothesis Generation', desc: 'Creates novel ideas' },
              { icon: RiFileTextLine, title: 'LaTeX Export', desc: 'Publication-ready report' },
            ].map((item, i) => (
              <div key={i} className="text-center">
                <div className="w-12 h-12 rounded-[14px] bg-orange2/10 flex items-center justify-center mx-auto mb-3">
                  <item.icon className="w-6 h-6 text-orange1" />
                </div>
                <p className="typo-body-strong text-primary mb-1">{item.title}</p>
                <p className="typo-small text-secondary">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Writing Intelligence Section */}
      <section id="writing" ref={writingRef} className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-2 rounded-full bg-green3 typo-small-strong text-green1 mb-4">
              Writing Intelligence
            </span>
            <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-4">
              Just ask. The AI writes your paper.
            </h2>
            <p className="typo-large text-secondary max-w-3xl mx-auto">
              Describe your intent in natural language — the agent drafts, edits, and formats your manuscript.
              You only decide: accept or reject. That&apos;s it.
            </p>
          </div>

          {/* Human-in-the-Loop Visual */}
          <div className="grid lg:grid-cols-2 gap-12 items-center mb-20">
            {/* Left: Pending Edit Interface */}
            <div className="writing-tool">
              <div className="rounded-[30px] border border-black/6 bg-fill-secondary overflow-hidden shadow-xl">
                {/* Mock Editor Header */}
                <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-black/6">
                  <div className="flex gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-400" />
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <div className="w-3 h-3 rounded-full bg-green-400" />
                  </div>
                  <div className="flex-1 text-center typo-small text-tertiary">main.tex</div>
                </div>

                {/* Pending Edit Banner */}
                <div className={`bg-orange2 px-5 py-3 flex items-center justify-between transition-all duration-500 ${writingPhase >= 1 ? 'opacity-100' : 'opacity-50'}`}>
                  <div className="flex items-center gap-2">
                    <RiQuillPenLine className="w-4 h-4 text-orange1" />
                    <span className="typo-small-strong text-orange1">Pending Edit — Lines 23-27 will be modified</span>
                  </div>
                  <div className={`flex items-center gap-2 transition-all duration-300 ${writingPhase >= 3 ? 'opacity-100' : 'opacity-50'}`}>
                    <button className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-red-500 hover:bg-red-600 text-white typo-small-strong transition-colors">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Reject
                    </button>
                    <button className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-green2 hover:bg-green1 text-white typo-small-strong transition-colors">
                      <RiCheckLine className="w-4 h-4" />
                      Accept
                    </button>
                  </div>
                </div>

                {/* Code Diff View */}
                <div className="bg-editor-bg p-5 font-mono text-sm">
                  {/* Unchanged lines */}
                  <div className="text-editor-muted opacity-60 mb-2">
                    <span className="inline-block w-8 text-right mr-4 opacity-50">21</span>
                    <span>\section&#123;Methodology&#125;</span>
                  </div>
                  <div className="text-editor-muted opacity-60 mb-4">
                    <span className="inline-block w-8 text-right mr-4 opacity-50">22</span>
                    <span></span>
                  </div>

                  {/* Deleted lines (red) - appear one by one */}
                  {deletionLines >= 1 && (
                    <div className="bg-red-500/10 border-l-4 border-red-500 -mx-5 px-5 py-0.5 mb-1 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-red-400 opacity-70">23</span>
                      <span className="text-red-400 line-through">We propose a simple baseline that uses</span>
                    </div>
                  )}
                  {deletionLines >= 2 && (
                    <div className="bg-red-500/10 border-l-4 border-red-500 -mx-5 px-5 py-0.5 mb-3 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-red-400 opacity-70">24</span>
                      <span className="text-red-400 line-through">standard attention mechanisms.</span>
                    </div>
                  )}

                  {/* Added lines (green) - appear one by one */}
                  {additionLines >= 1 && (
                    <div className="bg-green-500/10 border-l-4 border-green-500 -mx-5 px-5 py-0.5 mb-1 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-green-400">+</span>
                      <span className="text-green-400">We introduce a novel hierarchical approach</span>
                    </div>
                  )}
                  {additionLines >= 2 && (
                    <div className="bg-green-500/10 border-l-4 border-green-500 -mx-5 px-5 py-0.5 mb-1 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-green-400">+</span>
                      <span className="text-green-400">that combines multi-scale feature extraction</span>
                    </div>
                  )}
                  {additionLines >= 3 && (
                    <div className="bg-green-500/10 border-l-4 border-green-500 -mx-5 px-5 py-0.5 mb-1 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-green-400">+</span>
                      <span className="text-green-400">with adaptive attention weights, enabling</span>
                    </div>
                  )}
                  {additionLines >= 4 && (
                    <div className="bg-green-500/10 border-l-4 border-green-500 -mx-5 px-5 py-0.5 mb-4 animate-fade-in-up">
                      <span className="inline-block w-8 text-right mr-4 text-green-400">+</span>
                      <span className="text-green-400">robust performance across diverse inputs.</span>
                    </div>
                  )}

                  {/* More unchanged */}
                  <div className={`text-editor-muted opacity-60 transition-all duration-300 ${writingPhase >= 3 ? 'opacity-60' : 'opacity-0'}`}>
                    <span className="inline-block w-8 text-right mr-4 opacity-50">28</span>
                    <span></span>
                  </div>
                  <div className="text-editor-muted opacity-60">
                    <span className="inline-block w-8 text-right mr-4 opacity-50">29</span>
                    <span>\subsection&#123;Architecture&#125;</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Messaging */}
            <div className="writing-tool">
              <h3 className="font-youware-sans text-3xl font-medium text-primary mb-6">
                HITL by design
              </h3>
              <p className="typo-large text-secondary mb-8">
                You stay in control. Every AI-generated edit appears as a pending change.
                Review the diff, then accept or reject with one click.
                No surprises, no overwriting your work.
              </p>

              <div className="space-y-4">
                {[
                  { title: 'Vibe your intent', desc: 'Type what you want in natural language. The agent understands context.' },
                  { title: 'Review the diff', desc: 'See exactly what will change before it happens. Line by line.' },
                  { title: 'Accept or reject', desc: 'One click to apply. One click to dismiss. You decide.' },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-4 p-4 rounded-[16px] bg-fill-secondary">
                    <div className="w-8 h-8 rounded-full bg-green2 flex items-center justify-center flex-shrink-0 typo-body-strong text-white">
                      {i + 1}
                    </div>
                    <div>
                      <h4 className="typo-body-strong text-primary mb-1">{item.title}</h4>
                      <p className="typo-small text-secondary">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Writing Tools Grid */}
          <div className="text-center mb-8">
            <h3 className="typo-h2 text-primary mb-2">Generate any LaTeX element</h3>
            <p className="typo-body text-secondary">From tables to algorithms — just describe what you need.</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {writingTools.map((tool, index) => (
              <div
                key={index}
                className="writing-tool flex flex-col items-center gap-3 p-5 rounded-[20px] border border-black/6 bg-fill-secondary hover:bg-white hover:border-green2/20 transition-all duration-300"
              >
                <div className="w-12 h-12 rounded-[12px] bg-white border border-black/6 flex items-center justify-center">
                  <tool.icon className="w-6 h-6 text-green2" />
                </div>
                <div className="text-center">
                  <h4 className="typo-small-strong text-primary">{tool.name}</h4>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-24 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-2 rounded-full bg-green3 typo-small-strong text-green1 mb-4">
              FAQ
            </span>
            <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-primary mb-4">
              Common questions
            </h2>
          </div>

          <div className="space-y-4">
            {[
              {
                q: 'Is YouResearch really free?',
                a: 'Yes, YouResearch is free and open source. The AI features use the Anthropic API which requires an API key.',
              },
              {
                q: 'Does it work offline?',
                a: 'Yes! YouResearch compiles LaTeX locally using Tectonic. You only need internet for AI features and paper search.',
              },
              {
                q: 'What about my data privacy?',
                a: 'Your documents never leave your machine. AI conversations are sent to Anthropic but not stored. No telemetry, no cloud storage.',
              },
              {
                q: 'Can I use it with Overleaf?',
                a: 'Absolutely. YouResearch syncs with Overleaf via Git, so you can edit locally and push changes to collaborate with others.',
              },
              {
                q: 'Which LaTeX packages are supported?',
                a: 'YouResearch uses Tectonic which automatically downloads packages on-demand. Most common packages work out of the box.',
              },
            ].map((item, index) => (
              <div
                key={index}
                className="rounded-[20px] border border-black/6 bg-white p-6 hover:border-green2/20 transition-colors"
              >
                <h3 className="typo-body-strong text-primary mb-2">{item.q}</h3>
                <p className="typo-body text-secondary">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section ref={ctaRef} className="py-24 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="cta-content rounded-[30px] bg-green2 p-12 md:p-16 text-center relative overflow-hidden">
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-10">
              <div className="absolute top-0 left-0 w-64 h-64 bg-white rounded-full -translate-x-1/2 -translate-y-1/2" />
              <div className="absolute bottom-0 right-0 w-96 h-96 bg-white rounded-full translate-x-1/3 translate-y-1/3" />
            </div>

            <div className="relative">
              <h2 className="font-youware-sans text-4xl md:text-5xl font-medium text-white mb-4">
                Start writing smarter
              </h2>
              <p className="typo-large text-white/80 max-w-xl mx-auto mb-8">
                Download YouResearch for free. Your documents, your machine, your research agent.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <button className="flex items-center gap-2 bg-white text-green2 hover:bg-green3 rounded-full px-8 py-4 typo-body-strong transition-all hover:shadow-lg">
                  <RiMacLine className="w-5 h-5" />
                  Download for macOS
                </button>
                <button className="flex items-center gap-2 border border-white/30 text-white hover:bg-white/10 rounded-full px-8 py-4 typo-body transition-colors">
                  View Documentation
                  <RiArrowRightLine className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-black/6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-[10px] bg-green2 flex items-center justify-center">
              <RiQuillPenLine className="w-5 h-5 text-white" />
            </div>
            <span className="typo-body-strong text-primary">YouResearch</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="typo-small text-secondary hover:text-primary transition-colors">GitHub</a>
            <a href="#" className="typo-small text-secondary hover:text-primary transition-colors">Documentation</a>
            <a href="#" className="typo-small text-secondary hover:text-primary transition-colors">Privacy</a>
          </div>
          <p className="typo-small text-tertiary">
            Built with Claude AI
          </p>
        </div>
      </footer>
    </div>
  );
}

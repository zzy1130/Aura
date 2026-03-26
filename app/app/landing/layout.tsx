import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'YouResearch - The LaTeX IDE that researches with you',
  description: 'A local-first macOS app that combines a professional LaTeX editor with an AI research agent. Explore literature deeper, discover ideas faster.',
};

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

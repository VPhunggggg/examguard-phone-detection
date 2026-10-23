import AboutSection from '../components/AboutSection'
import FeaturedDemoSection from '../components/FeaturedDemoSection'
import FinalCTASection from '../components/FinalCTASection'
import HeroSection from '../components/HeroSection'
import PhilosophySection from '../components/PhilosophySection'
import ServicesSection from '../components/ServicesSection'

function LandingPage() {
  return (
    <>
      <HeroSection />
      <main>
        <AboutSection />
        <FeaturedDemoSection />
        <PhilosophySection />
        <ServicesSection />
        <FinalCTASection />
      </main>
    </>
  )
}

export default LandingPage

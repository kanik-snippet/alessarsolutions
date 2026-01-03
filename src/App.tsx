import Hero from './components/Hero';
import Services from './components/Services';
import Products from './components/Products';
import Technologies from './components/Technologies';
import About from './components/About';
import Team from './components/Team';
import Contact from './components/Contact';
import Footer from './components/Footer';
import Navbar from './components/Navbar';

function App() {
  return (
    <div className="min-h-screen bg-black text-white">
      <Navbar />
      <Hero />
      <Services />
      <Products />
      <Technologies />
      <About />
      <Team />
      <Contact />
      <Footer />
    </div>
  );
}

export default App;

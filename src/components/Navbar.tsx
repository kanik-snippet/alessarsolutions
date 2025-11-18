import { Menu, X } from 'lucide-react';
import { useState } from 'react';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    element?.scrollIntoView({ behavior: 'smooth' });
    setIsOpen(false);
  };

  return (
    <nav className="fixed w-full top-0 z-50 bg-black/80 backdrop-blur-lg border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex-shrink-0 flex items-center">
            <span className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              Alessar Solutions
            </span>
          </div>

          <div className="hidden md:flex space-x-8">
            <button onClick={() => scrollToSection('home')} className="hover:text-cyan-400 transition-colors">Home</button>
            <button onClick={() => scrollToSection('services')} className="hover:text-cyan-400 transition-colors">Services</button>
            <button onClick={() => scrollToSection('products')} className="hover:text-cyan-400 transition-colors">Products</button>
            <button onClick={() => scrollToSection('about')} className="hover:text-cyan-400 transition-colors">About</button>
            <button onClick={() => scrollToSection('contact')} className="hover:text-cyan-400 transition-colors">Contact</button>
          </div>

          <div className="md:hidden">
            <button onClick={() => setIsOpen(!isOpen)} className="text-white">
              {isOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </div>

      {isOpen && (
        <div className="md:hidden bg-black/95 border-t border-gray-800">
          <div className="px-2 pt-2 pb-3 space-y-1">
            <button onClick={() => scrollToSection('home')} className="block w-full text-left px-3 py-2 hover:bg-gray-900 rounded">Home</button>
            <button onClick={() => scrollToSection('services')} className="block w-full text-left px-3 py-2 hover:bg-gray-900 rounded">Services</button>
            <button onClick={() => scrollToSection('products')} className="block w-full text-left px-3 py-2 hover:bg-gray-900 rounded">Products</button>
            <button onClick={() => scrollToSection('about')} className="block w-full text-left px-3 py-2 hover:bg-gray-900 rounded">About</button>
            <button onClick={() => scrollToSection('contact')} className="block w-full text-left px-3 py-2 hover:bg-gray-900 rounded">Contact</button>
          </div>
        </div>
      )}
    </nav>
  );
}

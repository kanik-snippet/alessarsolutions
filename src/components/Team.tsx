import { useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Linkedin, Github, Mail } from 'lucide-react';

const teamMembers = [
  {
    id: 1,
    name: 'Your Name',
    role: 'Founder & CEO',
    description: 'Visionary leader passionate about transforming ideas into innovative digital solutions.',
    image: 'https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
  {
    id: 2,
    name: 'Team Member 1',
    role: 'Lead Developer',
    description: 'Expert in full-stack development with 5+ years of experience building scalable applications.',
    image: 'https://images.pexels.com/photos/1181690/pexels-photo-1181690.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
  {
    id: 3,
    name: 'Team Member 2',
    role: 'Mobile Developer',
    description: 'Specialized in React Native and Flutter, creating seamless mobile experiences.',
    image: 'https://images.pexels.com/photos/1239291/pexels-photo-1239291.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
  {
    id: 4,
    name: 'Team Member 3',
    role: 'UI/UX Designer',
    description: 'Creative designer focused on crafting beautiful and intuitive user experiences.',
    image: 'https://images.pexels.com/photos/1239291/pexels-photo-1239291.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
  {
    id: 5,
    name: 'Team Member 4',
    role: 'Backend Engineer',
    description: 'Database architect and API specialist ensuring robust and efficient systems.',
    image: 'https://images.pexels.com/photos/1181690/pexels-photo-1181690.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
  {
    id: 6,
    name: 'Team Member 5',
    role: 'DevOps Specialist',
    description: 'Cloud infrastructure expert managing deployment and system reliability.',
    image: 'https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=400',
  },
];

export default function Team() {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showLeftArrow, setShowLeftArrow] = useState(false);
  const [showRightArrow, setShowRightArrow] = useState(true);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;

    const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
    setShowLeftArrow(scrollLeft > 0);
    setShowRightArrow(scrollLeft < scrollWidth - clientWidth - 10);
  };

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;

    const scrollAmount = 400;
    scrollContainerRef.current.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });
  };

  return (
    <section className="py-20 bg-gradient-to-b from-black to-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            Meet Our Team
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Talented professionals dedicated to delivering excellence and innovation
          </p>
        </div>

        <div className="relative">
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex overflow-x-auto gap-6 pb-4 scrollbar-hide"
            style={{
              scrollBehavior: 'smooth',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
            }}
          >
            {teamMembers.map((member) => (
              <div
                key={member.id}
                className="flex-shrink-0 w-72 group"
              >
                <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-2xl overflow-hidden hover:border-cyan-500/50 transition-all duration-300 hover:transform hover:scale-105 h-full flex flex-col">
                  <div className="h-56 relative overflow-hidden">
                    <img
                      src={member.image}
                      alt={member.name}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-gray-900 via-transparent to-transparent"></div>
                  </div>

                  <div className="px-6 py-6 flex flex-col flex-grow">
                    <h3 className="text-xl font-semibold text-white mb-1 group-hover:text-cyan-400 transition-colors">
                      {member.name}
                    </h3>
                    <p className="text-cyan-400 text-sm font-medium mb-3">
                      {member.role}
                    </p>

                    <p className="text-gray-400 text-sm leading-relaxed flex-grow mb-4">
                      {member.description}
                    </p>

                    <div className="flex space-x-3 pt-4 border-t border-gray-700">
                      <a
                        href="#"
                        className="flex-1 bg-gray-700/50 hover:bg-gray-700 rounded-lg p-2 flex items-center justify-center transition-colors text-gray-400 hover:text-cyan-400"
                        title="LinkedIn"
                      >
                        <Linkedin className="w-4 h-4" />
                      </a>
                      <a
                        href="#"
                        className="flex-1 bg-gray-700/50 hover:bg-gray-700 rounded-lg p-2 flex items-center justify-center transition-colors text-gray-400 hover:text-cyan-400"
                        title="GitHub"
                      >
                        <Github className="w-4 h-4" />
                      </a>
                      <a
                        href="#"
                        className="flex-1 bg-gray-700/50 hover:bg-gray-700 rounded-lg p-2 flex items-center justify-center transition-colors text-gray-400 hover:text-cyan-400"
                        title="Email"
                      >
                        <Mail className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {showLeftArrow && (
            <button
              onClick={() => scroll('left')}
              className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-4 z-10 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white p-3 rounded-full shadow-lg transition-all duration-300 hover:scale-110"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>
          )}

          {showRightArrow && (
            <button
              onClick={() => scroll('right')}
              className="absolute right-0 top-1/2 transform -translate-y-1/2 translate-x-4 z-10 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white p-3 rounded-full shadow-lg transition-all duration-300 hover:scale-110"
            >
              <ChevronRight className="w-6 h-6" />
            </button>
          )}
        </div>

        <p className="text-center text-gray-500 text-sm mt-8">
          Scroll to see more team members →
        </p>
      </div>
    </section>
  );
}

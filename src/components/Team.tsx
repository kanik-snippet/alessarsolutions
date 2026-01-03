import { useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Linkedin, Github, Mail } from 'lucide-react';

const teamMembers = [
  {
    id: 1,
    name: 'Your Name',
    role: 'Founder & CEO',
    description: 'Visionary leader passionate about transforming ideas into innovative digital solutions.',
    initials: 'YN',
    color: 'from-blue-600 to-cyan-600',
  },
  {
    id: 2,
    name: 'Team Member 1',
    role: 'Lead Developer',
    description: 'Expert in full-stack development with 5+ years of experience building scalable applications.',
    initials: 'TM',
    color: 'from-purple-600 to-pink-600',
  },
  {
    id: 3,
    name: 'Team Member 2',
    role: 'Mobile Developer',
    description: 'Specialized in React Native and Flutter, creating seamless mobile experiences.',
    initials: 'MD',
    color: 'from-green-600 to-teal-600',
  },
  {
    id: 4,
    name: 'Team Member 3',
    role: 'UI/UX Designer',
    description: 'Creative designer focused on crafting beautiful and intuitive user experiences.',
    initials: 'UD',
    color: 'from-orange-600 to-red-600',
  },
  {
    id: 5,
    name: 'Team Member 4',
    role: 'Backend Engineer',
    description: 'Database architect and API specialist ensuring robust and efficient systems.',
    initials: 'BE',
    color: 'from-indigo-600 to-blue-600',
  },
  {
    id: 6,
    name: 'Team Member 5',
    role: 'DevOps Specialist',
    description: 'Cloud infrastructure expert managing deployment and system reliability.',
    initials: 'DS',
    color: 'from-yellow-600 to-orange-600',
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
                  <div className={`h-32 bg-gradient-to-br ${member.color} relative overflow-hidden`}>
                    <div className="absolute inset-0 opacity-30 group-hover:opacity-50 transition-opacity">
                      <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent"></div>
                    </div>
                  </div>

                  <div className="px-6 py-6 flex flex-col flex-grow">
                    <div className="flex items-center space-x-4 mb-4">
                      <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${member.color} flex items-center justify-center text-white font-bold text-xl border-4 border-gray-800 transform -translate-y-8 shadow-lg`}>
                        {member.initials}
                      </div>
                    </div>

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

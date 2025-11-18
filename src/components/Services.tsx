import {
  Globe,
  Smartphone,
  Monitor,
  Bot,
  MessageSquare,
  Code2,
  Database,
  Cloud,
  Zap,
  Palette,
  ShoppingCart,
  Lock
} from 'lucide-react';

const services = [
  {
    icon: Globe,
    title: 'Web Applications',
    description: 'Modern, responsive, and scalable web applications built with cutting-edge technologies.',
  },
  {
    icon: Smartphone,
    title: 'Mobile Applications',
    description: 'Native and cross-platform mobile apps for iOS and Android that engage users.',
  },
  {
    icon: Monitor,
    title: 'Desktop Applications',
    description: 'Powerful desktop software solutions for Windows, macOS, and Linux platforms.',
  },
  {
    icon: Bot,
    title: 'AI Chatbots',
    description: 'Intelligent conversational AI chatbots that enhance customer engagement and support.',
  },
  {
    icon: MessageSquare,
    title: 'Telegram Bots',
    description: 'Custom Telegram bots for automation, notifications, and interactive experiences.',
  },
  {
    icon: Code2,
    title: 'Custom Software',
    description: 'Tailored software solutions designed specifically for your unique business needs.',
  },
  {
    icon: Database,
    title: 'Database Solutions',
    description: 'Robust database architecture and management for optimal data handling.',
  },
  {
    icon: Cloud,
    title: 'Cloud Services',
    description: 'Cloud infrastructure setup, migration, and management for scalable operations.',
  },
  {
    icon: Zap,
    title: 'API Development',
    description: 'RESTful and GraphQL APIs that power seamless integrations and data exchange.',
  },
  {
    icon: Palette,
    title: 'UI/UX Design',
    description: 'Beautiful, intuitive user interfaces that provide exceptional user experiences.',
  },
  {
    icon: ShoppingCart,
    title: 'E-Commerce Solutions',
    description: 'Complete e-commerce platforms with payment integration and inventory management.',
  },
  {
    icon: Lock,
    title: 'Security Solutions',
    description: 'Comprehensive security implementations to protect your applications and data.',
  },
];

export default function Services() {
  return (
    <section id="services" className="py-20 bg-gradient-to-b from-black to-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            Our Services
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Whatever you need, we can build it. From concept to deployment, we deliver excellence.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {services.map((service, index) => (
            <div
              key={index}
              className="group bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6 hover:bg-gray-800 hover:border-cyan-500/50 transition-all duration-300 hover:transform hover:scale-105"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-600 rounded-lg flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
                <service.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-white group-hover:text-cyan-400 transition-colors">
                {service.title}
              </h3>
              <p className="text-gray-400">{service.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

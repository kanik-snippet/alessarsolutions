import { Target, Users, Lightbulb, TrendingUp } from 'lucide-react';

export default function About() {
  return (
    <section id="about" className="py-20 bg-gradient-to-b from-black to-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            About Alessar Solutions
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Your trusted partner in digital transformation
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-12 mb-16">
          <div>
            <h3 className="text-2xl font-bold text-white mb-4">Who We Are</h3>
            <p className="text-gray-400 mb-4">
              Alessar Solutions is a forward-thinking technology company dedicated to transforming ideas into powerful digital solutions. We specialize in creating custom software that drives business growth and innovation.
            </p>
            <p className="text-gray-400 mb-4">
              Our team of experienced developers, designers, and strategists work collaboratively to deliver solutions that exceed expectations. From startups to enterprises, we've helped numerous clients achieve their digital goals.
            </p>
            <p className="text-gray-400">
              We believe in the power of technology to solve real-world problems, and we're committed to building solutions that make a meaningful impact.
            </p>
          </div>

          <div className="space-y-6">
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <Target className="w-6 h-6 text-white" />
              </div>
              <div>
                <h4 className="text-xl font-semibold text-white mb-2">Our Mission</h4>
                <p className="text-gray-400">
                  To empower businesses with innovative technology solutions that drive growth, efficiency, and competitive advantage.
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <Lightbulb className="w-6 h-6 text-white" />
              </div>
              <div>
                <h4 className="text-xl font-semibold text-white mb-2">Our Vision</h4>
                <p className="text-gray-400">
                  To be the leading technology partner for businesses seeking innovative and reliable digital solutions.
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <Users className="w-6 h-6 text-white" />
              </div>
              <div>
                <h4 className="text-xl font-semibold text-white mb-2">Our Values</h4>
                <p className="text-gray-400">
                  Excellence, innovation, integrity, and customer success are at the core of everything we do.
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <TrendingUp className="w-6 h-6 text-white" />
              </div>
              <div>
                <h4 className="text-xl font-semibold text-white mb-2">Our Approach</h4>
                <p className="text-gray-400">
                  Agile, collaborative, and results-driven methodologies that ensure successful project delivery.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
            <div className="text-4xl font-bold text-cyan-400 mb-2">73</div>
            <div className="text-gray-400">Projects Delivered</div>
          </div>
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
            <div className="text-4xl font-bold text-cyan-400 mb-2">18</div>
            <div className="text-gray-400">Happy Clients</div>
          </div>
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
            <div className="text-4xl font-bold text-cyan-400 mb-2">24/7</div>
            <div className="text-gray-400">Support Available</div>
          </div>
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
            <div className="text-4xl font-bold text-cyan-400 mb-2">99%</div>
            <div className="text-gray-400">Client Satisfaction</div>
          </div>
        </div>
      </div>
    </section>
  );
}
